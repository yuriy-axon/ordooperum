---
name: new-task
description: Capture tasks from free-form text, dictated audio, or emails and messages from other people, in any language (Polish, Russian, Ukrainian, …). Detects every task, polishes it into English, assigns tier and project, blocks duplicates, enriches it with project context and internet research, and saves it to data/tasks/. Use when the user runs /new-task, asks to add, capture or record tasks, or pastes an email or message and asks what to do with it.
---

# New Task

Turn the user's input into complete, polished tasks in `data/tasks/`, so later agents can prioritize, schedule and execute them without the original input. File formats and allowed values are in `docs/data-model.md`. This skill only captures tasks: it doesn't plan or reorganize them.

## Input

The text after `/new-task`. If there is none, ask the user to paste or dictate it, and wait.
`source` is `audio` if the user says it was dictated or it reads like a raw transcript (no punctuation, filler words); otherwise `text`.

The input can be in any language, and it can be either:
- **the user's own notes** — every actionable item is a task for the user;
- **someone else's communication** forwarded or pasted by the user (an email, chat, letter, meeting notes) — tasks are what the user needs to do because of it.

## Steps

1. **Load.** Read `data/profile.md` (the user's location, time zone, currency) and all files in `data/projects/` and `data/tasks/`.

2. **Detect.** Read the whole input in its own language and understand it before extracting anything. Find every distinct actionable item. Merge repeats within this input. Non-task content only enriches descriptions.

   For someone else's communication, work out from context:
   - **Who** wrote it, to whom, and what they want. The user is the reader unless the text says otherwise.
   - **Explicit requests** to the user ("please send…", "prześlij…", "пришли…", "надішліть…") → tasks.
   - **Implied actions**: a question that needs an answer → "Reply to <name> about <topic>"; a document to review, sign or pay; a meeting to confirm; a deadline the user must meet.
   - **Commitments the user made** in a quoted earlier reply ("I'll send it tomorrow") → tasks.
   - **Things others will do** are not tasks, unless the user clearly needs to check on them → "Follow up with <name> on <topic>" only when the text gives a date or a reason to follow up.
   - **Ignore** greetings, signatures, disclaimers, ads, and quoted history that has already been handled.
   - Put the sender, their role or company, and the key facts (amounts, reference numbers, places, deadlines) into the description, translated into English. Keep names, company names and reference numbers exactly as written.

3. **Draft each task** in polished English, without changing the meaning:
   - **Title** and **Description** per the data model. The description says what, why, who, and what "done" looks like, as far as the input allows.
   - **Priority** from the wording; `P3` when there is no signal:
     - `P1` — "ASAP", "urgent", "critical", something broken, people blocked, serious consequences. Use sparingly.
     - `P2` — a deadline within days, "important", "soon".
     - `P4` — "no rush", "sometime this year".
     - `P5` — "someday", "would be nice", "if I ever have time".
   - **Due** only if stated or clearly implied, in any language ("do piątku", "до пятницы", "до кінця місяця"). Resolve relative dates against the message's own date if it shows one, otherwise against today.
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

6. **Enrich** each task being saved, so the user can act on it without searching themselves. Use WebSearch / WebFetch; prefer official sources (the company's own site, government portals, official price lists). Every internet fact gets a source link and today's date.
   - `Project:` — facts from the project's Context that help with this task.
   - `Place:` — whenever the task means going somewhere or contacting an organization (bank, post office, courier, office, shop, clinic, authority):
     - Find the 1–3 options nearest to the user's location from the profile (or the place the task names), each with name, address, opening hours (note days closed, lunch breaks, appointment-only), and phone or booking link.
     - If the organization has no branch near the user (e.g. a bank in another country), give the remote way instead: online banking, app, hotline or email, with its hours and the user's time zone.
     - Say if an appointment, ID or documents are needed.
   - `Price:` — whenever the task may involve paying (buying, fees, shipping, licences, subscriptions, services, fines):
     - Find current prices from official sources, in the profile currency (keep the original currency too if different).
     - For purchases, compare 2–3 offers; for services, give the price range or the specific tariff that applies.
     - Mark prices as indicative and note what they depend on (size, weight, plan, number of users).
   - `Research:` — other facts that help get it done: procedures, required documents, deadlines, regulations.
   - At most 8 bullets in total; only what's useful for this task.
   - Search queries may include the user's city and region. Never put private details in a query: names, street addresses, account or reference numbers, health data.
   - `None.` if nothing applies.

7. **Save.** For each new task, get the ID from `python3 scripts/validate.py --next-id`, then write the file. Then run `python3 scripts/validate.py` and fix every error.

8. **Report** a table — ID, title, tier, project, priority, due, result (`created`, `updated`, `already exists as T-NNNN`, `skipped`) — and one line inviting corrections. Nothing else.

## Rules

- Questions only for: an unclear tier or project, a new project, a partially similar task, input too vague to name any task, or communication where it's unclear whether something is the user's job. Everything else is saved without confirmation.
- No tasks in the input: say so and save nothing.
- Change existing tasks only when the user picks **Update existing** or asks for a correction. Never change existing projects.
