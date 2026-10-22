"""Draft a message to whoever a task involves, with Claude. Used by POST /api/tasks/<id>/draft.

Needs the Anthropic SDK (`pip install anthropic`) and credentials (ANTHROPIC_API_KEY or `ant auth login`).
Only this feature needs them; the rest of the app stays dependency-free.
"""

MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "needs_language": {"type": "boolean"},
        "language": {"type": "string"},
        "recipient": {"type": "string"},
        "subject": {"type": "string"},
        "body": {"type": "string"},
    },
    "required": ["needs_language", "language", "recipient", "subject", "body"],
    "additionalProperties": False,
}

SYSTEM = """You draft short messages (emails or chat messages) that the user sends to someone about one of their tasks.

Write a fresh, complete message: greeting, the point, any request or next step, and a sign-off. Keep it short, polite and natural, the way a busy professional writes.

Language: write in the language the recipient uses. Work it out from the task: the language of a message the recipient wrote (quoted in the original input), the recipient's name or organisation, or the country they are in. If the user names a language, use it. If you cannot tell with reasonable confidence, set needs_language to true and leave subject and body empty; do not guess.

Facts: use only what the task says. Never invent names, amounts, dates, reference numbers or promises. Where a needed detail is missing, put a short placeholder in square brackets, e.g. [date], [amount]. Sign off without a name unless the task shows the user's name.

recipient: who the message is for, as the task describes them (e.g. "the accountant", "Slava"), or "" if nobody is clear. language: the language's English name, e.g. "Italian". subject: a short subject line in the same language (for chat messages it may be ""). body: the message text only."""


class DraftError(Exception):
    pass


def draft_message(task, profile, language=None):
    """task: dict with title, description, additional_info, original_input, project_name.
    Returns the parsed JSON dict described by SCHEMA."""
    try:
        import anthropic
    except ImportError:
        raise DraftError("The Anthropic SDK is not installed. Run: pip install anthropic")

    prompt = "\n\n".join(filter(None, [
        f"Task: {task.get('title')}",
        f"Project: {task.get('project_name')}",
        f"Description:\n{task.get('description')}",
        f"Additional information:\n{task.get('additional_info')}",
        f"Original input (the user's words, or a message they received):\n{task.get('original_input')}",
        f"The user lives in: {profile.get('location')}" if profile.get("location") else "",
        f"Write the message in {language}." if language else "",
    ]))

    try:
        client = anthropic.Anthropic()
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",  # if Claude declines, Anthropic retries on its recommended fallback model
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": SCHEMA}},
            system=SYSTEM,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.AuthenticationError:
        raise DraftError("No valid Anthropic credentials. Set ANTHROPIC_API_KEY or run `ant auth login`.")
    except anthropic.RateLimitError:
        raise DraftError("Rate limited by the Anthropic API. Try again in a minute.")
    except anthropic.APIStatusError as e:
        raise DraftError(f"Anthropic API error {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise DraftError("Could not reach the Anthropic API. Check your internet connection.")

    if response.stop_reason == "refusal":
        raise DraftError("Claude declined to draft this message.")
    if response.stop_reason == "max_tokens":
        raise DraftError("The draft was cut off. Try again.")

    import json
    text = next((b.text for b in response.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except ValueError:
        raise DraftError("Claude returned an unexpected answer. Try again.")
