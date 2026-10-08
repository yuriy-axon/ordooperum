---
name: meeting
description: Prepare for a meeting. Turns the user's brief (any language, typed or dictated) into a meeting plan with a goal and prioritized agenda items, each with a short description, key points, supporting material, likely questions and the outcome wanted — enriched from projects, open tasks, earlier meetings and internet research. Saves to data/meetings/. Use when the user runs /meeting or asks to prepare, plan or get ready for a meeting.
argument-hint: "<what you want to talk about, with whom>"
---

# Meeting

Turn the user's brief into a meeting plan that makes them well prepared: clear goal, prioritized agenda, and the material to back each point. Format and allowed values are in `docs/data-model.md` (Meetings). This skill doesn't create tasks by itself.

## Input

The text after `/meeting`: what the user wants to talk about, with whom, and anything else (date, length, project, worries, numbers). Any language. If there is none, ask for it and wait.
If the brief refers to a meeting that already exists in `data/meetings/` (same audience and topic, or the user says "update"), update that plan instead of creating a new one.

## Steps

1. **Load** `data/projects/`, open tasks in `data/tasks/`, and earlier meetings in `data/meetings/` with the same audience or project.

2. **Check what's missing.** The plan needs: **audience**, **goal** (what the meeting should achieve), and **duration**. Also useful: **date** and **project**. If the audience or goal is unclear, or the duration isn't given, ask — one AskUserQuestion call for all of them (offer 30 / 45 / 60 min for duration; existing projects as `Name (tier)` plus "No project"). Never guess them. A missing date is fine: use `null`.

3. **Build the agenda** from the brief, in polished English:
   - Split it into distinct topics. Add a topic the user didn't mention only if it's clearly needed (e.g. open action items from the last meeting with this audience) and say so in its description.
   - Give each a priority: `P1` must cover, `P2` should cover, `P3` if time allows — based on the user's emphasis, urgency, and the meeting goal.
   - Give each a time slot so the total fits the duration, P1 items first in time allocation. If P1 items alone don't fit, say so in the report.
   - Order items for a good discussion flow (context before decisions); usually P1 items early.
   - Each item has a 1–2 sentence description, then the four bullets from the data model.

4. **Enrich each item** — this is what makes the user better prepared:
   - **Key points**: the 2–4 things the user should say or make sure are understood, tailored to the audience (e.g. numbers and targets for sales, risks/costs/decisions for management).
   - **Supporting material**: facts the user can use, each marked with where it came from:
     - `Project:` facts from the project's Context.
     - `Task:` related open tasks — `T-NNNN title (priority, due)`.
     - `Last meeting:` open points or decisions from an earlier meeting with this audience.
     - `Research:` market, industry, competitor, regulation, best-practice or benchmark facts from WebSearch / WebFetch, each with source link and date. At most 3 per item; only where they genuinely strengthen the point. Never put confidential details (client names, internal numbers, personal data) in a search query; search the general topic.
     - `None.` if nothing applies.
   - **Likely questions**: 1–3 questions this audience will probably ask, each with a short suggested answer or what to check first.
   - **Outcome wanted**: the decision, agreement or next step this item should produce.

5. **Preparation**: list what the user should prepare, check or bring (numbers to pull, people to ask, documents to open). `None.` if nothing.

6. **Save** to `data/meetings/<date or "undated">-<slug>.md` with `status: planned`, timestamps from `date -Iseconds`, and the brief verbatim under Original brief. Run `python3 scripts/validate.py` and fix every error.

7. **Show the plan** in chat: title, audience, date, duration, goal, then the agenda as a compact list (`1. Title — P1 · 15 min`: description) and the Preparation list. Don't show the Original brief. End with the file path and one question with AskUserQuestion: create tasks for the Preparation items? (**Yes, all** / **Let me choose** / **No**). On yes, create them following the `/new-task` rules (project and tier from the meeting, due = the day before the meeting if it has a date).

## Rules

- Never invent numbers, names, decisions or facts about the user's business. Use what the brief, projects, tasks and earlier meetings say; mark anything else as something to check ("Check: current Q4 win rate").
- Updating a plan: keep its `id` and `created`, set `updated`, append the new brief to Original brief.
- When the user says the meeting happened or was cancelled, set `status` to `done` or `cancelled` and `updated`.
