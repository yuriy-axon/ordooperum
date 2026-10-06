---
name: new-task
description: Capture tasks from free-form text or dictated audio. Detects every task, polishes it into English, assigns tier and project, blocks duplicates, enriches it with project context and internet research, and saves it to data/tasks/. Use when the user runs /new-task or asks to add, capture or record tasks.
---

# New Task

Turn the user's input into complete, polished tasks in `data/tasks/`, so later agents can prioritize, schedule and execute them without the original input. File formats and allowed values are in `docs/data-model.md`. This skill only captures tasks: it doesn't plan or reorganize them.

## Input

The text after `/new-task`. If there is none, ask the user to paste or dictate it, and wait.
`source` is `audio` if the user says it was dictated or it reads like a raw transcript (no punctuation, filler words); otherwise `text`.

## Steps

1. **Load.** Read all files in `data/projects/` and `data/tasks/`.

2. **Detect.** Find every distinct actionable item. Merge repeats within this input. Non-task content only enriches descriptions.

3. **Draft each task** in polished English, without changing the meaning:
   - **Title** and **Description** per the data model. The description says what, why, who, and what "done" looks like, as far as the input allows.
   - **Priority** from the wording; `P3` when there is no signal:
     - `P1` — "ASAP", "urgent", "critical", something broken, people blocked, serious consequences. Use sparingly.
     - `P2` — a deadline within days, "important", "soon".
     - `P4` — "no rush", "sometime this year".
     - `P5` — "someday", "would be nice", "if I ever have time".
   - **Due** only if stated or clearly implied; resolve relative dates ("Friday", "end of month") against today.
   - **Week** only if the input says when to do it ("this week", "next week", "in week 43"); then `pinned: true`. Otherwise `week: null`, `pinned: false`. `closed` is always `null`.
   - **Tier and project**: the existing project that clearly fits. If none does, or the input names a project that doesn't exist yet, mark it for a question.

4. **Check duplicates** by meaning against every existing task. No duplicates are allowed.
   - **Identical** (same action on the same thing, nothing new): drop the draft, leave the existing task untouched, report `already exists as T-NNNN`.
   - **Partially similar** (overlaps but adds detail, changes scope, deadline or priority, or could be a sub-task): mark it for a question.

5. **Ask** — one AskUserQuestion call for all open points (more calls only beyond 4 questions):
   - **Project**: options are the best 1–3 existing projects labelled `Name (tier)`, plus `Create "<name>" in <tier>` if the input named one. The user can type another name via Other. Ask the tier separately (`Business` / `Personal`) if it isn't obvious. Create a new project file only from a name the user gave or confirmed; Description and Context are `None yet.` unless the input says more.
   - **Similar task**: show both tasks (ID, title, priority). Options:
     - **Update existing** — keep its ID and `created`, set `updated`, append the new fragment to Original input, change title, priority, due or description only where the new input says so.
     - **Create separate** — save it as a new task.
     - **Skip** — discard it.

6. **Enrich** each task being saved:
   - `Project:` bullets with facts from the project's Context that help with this task.
   - `Research:` bullets from WebSearch / WebFetch, only when the task refers to something external whose details help get it done: a product, company, service, place, procedure, regulation, price, official deadline. At most 5 bullets, each with source link and date. Never put private details (names, addresses, account numbers, health data) in a search query.
   - `None.` if nothing applies.

7. **Save.** For each new task, get the ID from `python3 scripts/validate.py --next-id`, then write the file. Then run `python3 scripts/validate.py` and fix every error.

8. **Report** a table — ID, title, tier, project, priority, due, result (`created`, `updated`, `already exists as T-NNNN`, `skipped`) — and one line inviting corrections. Nothing else.

## Rules

- Questions only for: an unclear tier or project, a new project, a partially similar task, or input too vague to name any task. Everything else is saved without confirmation.
- No tasks in the input: say so and save nothing.
- Change existing tasks only when the user picks **Update existing** or asks for a correction. Never change existing projects.
