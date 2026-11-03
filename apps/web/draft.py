"""Draft a message to whoever a task involves, with Claude. Used by POST /api/tasks/<id>/draft.

Runs the Claude Code CLI (`claude -p`), so it uses your existing Claude Code login: no API key, no extra packages.
Needs `claude` on PATH and logged in.
"""

import json
import shutil
import subprocess
import tempfile

MODEL = "claude-opus-5-5"
TIMEOUT = 180  # seconds

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
    claude = shutil.which("claude")
    if not claude:
        raise DraftError("The Claude Code CLI (`claude`) was not found on PATH.")

    prompt = "\n\n".join(filter(None, [
        f"Task: {task.get('title')}",
        f"Project: {task.get('project_name')}",
        f"Description:\n{task.get('description')}",
        f"Additional information:\n{task.get('additional_info')}",
        f"Original input (the user's words, or a message they received):\n{task.get('original_input')}",
        f"The user lives in: {profile.get('location')}" if profile.get("location") else "",
        f"Write the message in {language}." if language else "",
    ]))

    cmd = [claude, "-p", "--model", MODEL, "--output-format", "json", "--tools", "",
           "--system-prompt", SYSTEM, "--json-schema", json.dumps(SCHEMA)]
    try:
        # Run outside the repo so the project's CLAUDE.md, skills and hooks are not loaded.
        proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True,
                              timeout=TIMEOUT, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        raise DraftError("Claude took too long to answer. Try again.")

    try:
        out = json.loads(proc.stdout)
    except ValueError:
        err = (proc.stderr or proc.stdout).strip()
        raise DraftError(f"Claude Code failed: {err[:300] or 'no output'}. Is `claude` logged in?")
    if out.get("is_error"):
        raise DraftError(f"Claude Code error: {str(out.get('result'))[:300]}")
    result = out.get("structured_output")
    if not isinstance(result, dict):
        raise DraftError("Claude returned an unexpected answer. Try again.")
    return result
