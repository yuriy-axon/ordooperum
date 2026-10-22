---
name: ordo
description: Plan meetings with the user's team and write their protocols. Before a meeting, turns the user's text (any language, typed or dictated) into a simple meeting plan — a goal and a list of talking points, each with a name and priority. After the meeting, turns the user's notes into a protocol with decisions, action items and open points, and proposes task changes. Links every task the user mentions by ID. Every meeting has a date and a name; the plan, notes and everything else for that date and name go into one file in data/meetings/. Use when the user runs /ordo, asks to prepare, plan or get ready for a meeting, or gives notes, minutes or a transcript of a meeting that happened.
argument-hint: "<what the meeting is about, with whom — or the notes after it>"
---

# Ordo

Ordo prepares the user for meetings with their team and records what came out of them. Formats and allowed values are in `docs/data-model.md` (Meetings, Tasks). Ordo never deletes anything and never changes a task without the user's confirmation.

## Input

The text after `/ordo`, in any language. If there is none, ask for it and wait. Decide the mode:

- **Plan**: what the user wants to discuss, with whom, and anything else (date, length, project, worries, numbers).
- **Protocol**: notes, minutes or a transcript of a meeting that already happened ("we agreed…", "Todd will…", "after the meeting"). To be asked for notes point by point instead, the user can run `/end-meeting`.

If the mode is unclear, ask.

## Which meeting

Every meeting is identified by its **date** and **name** (and **time**, if two meetings with the same name fall on one day); see Meetings in `docs/data-model.md`. Everything the user gives for that date and name — the plan, changes to it, notes, the protocol — goes into that one meeting file.

1. **Get date, name and time from the input.** Resolve relative dates ("tomorrow", "on Thursday", "yesterday") against today's date from `date -Iseconds` and the profile time zone. The name is what the user calls the meeting ("sales weekly", "sync with Todd"), written in title case (`Sales weekly`). Reuse the exact `name` of an earlier meeting in `data/meetings/` when the user clearly means the same series.
2. **Ask for what's missing.** If the date or name is missing or unclear, ask in one AskUserQuestion call before doing anything else (for the name, offer names of earlier meetings with the same audience, if any). Also ask for the start time if it isn't given; the user may skip it (`time: null`). Never guess a date or name.
3. **Find the file.** Look in `data/meetings/` for a meeting with the same `date` and `name`:
   - **One found** → work on it: keep its `id`, `name`, `date` and `created`; set `updated`; append the new input verbatim to Original input. A plan update rewrites the plan sections; notes go to Protocol mode on this file.
   - **Several found** (same name, different times) → match by time; if the input has no time, ask which one.
   - **None found** → create a new file named as in the data model. In Protocol mode, say there was no plan and write the protocol into the new file (Agenda then lists the topics actually discussed, as name and priority only).
   Never put input for one date and name into another meeting's file. If the user moves a meeting to another date or renames it, ask first, then rename the file to match and keep everything else.

## Same-name meetings

Before building any agenda or protocol, read **every** meeting in `data/meetings/` with the same `name` (all dates, planned, done and cancelled), oldest first. The new plan or protocol must continue that series consistently:

- **Structure and style**: the same goal phrasing, the same order and titles for recurring topics, a similar level of detail and tone, and the same way of writing action items and decisions. Reuse an earlier topic title word for word when the topic recurs.
- **Recurring topics**: topics that appear in most earlier meetings of the series ("as usual…") keep their usual place and priority unless the user says otherwise.
- **Continuity**: carry forward open points and unfinished action items from the latest protocol (and older ones still not closed) as agenda items (mentioned in the report with the date of the meeting they came from). In a protocol, note which earlier open points were settled.
- **Changes**: if the user's input departs from the series' usual pattern (a recurring topic dropped, a new format), follow the user and mention the change in the report.

If there are no earlier meetings with that name, say so in the report; this meeting sets the pattern for the series.

## Linking tasks

In both modes, find every task the user refers to, in any wording ("the Jira licenses thing", "bank card", "T-0007").

1. Match by ID, or by meaning against the titles and descriptions of all tasks in `data/tasks/` (open first; closed ones only if the input clearly refers to finished work).
2. If a mention could be more than one task, ask with AskUserQuestion (options: the closest 2–4 tasks as `T-NNNN — title`, plus `None of these`). Never guess.
3. Refer to linked tasks in the text as `T-NNNN title`, and list every linked ID in the `tasks` field.
4. A mention that matches no task is not a link. In Plan mode, keep it as plain text. In Protocol mode, it may become a proposed new task (step P4).

## Plan mode

1. **Load** `data/projects/`, `data/tasks/`, every meeting with the same name (see Same-name meetings), and other earlier meetings with the same audience or project.

2. **Check what's missing.** Besides date and name (see Which meeting), the plan needs the **audience**; **duration** and **project** are optional (`null` if not given). Ask only if the audience is unclear. Never guess it.

3. **Build the agenda** — keep it simple: each talking point is only its **name and priority**, as `### <n>. <title> — <priority>`, with nothing under it (no description, time slot, key points or research).
   - Split the input into distinct talking points, each named in a few words of polished English. Add a point the user didn't mention only for an open action item or open point from the last protocol of this series, and mention it in the report.
   - Priority: `P1` must cover, `P2` should cover, `P3` if time allows — from the user's emphasis, urgency and the priority of linked tasks.
   - Order: P1 points first, then P2, then P3; within a priority, the user's order.
   - **Goal**: one sentence summing up what the points should achieve, from the input.
   - **Preparation**: only what the user said to prepare; otherwise `None.`

4. **Save** to the file from Which meeting with `status: planned`, `Protocol` set to `None yet.`, timestamps from `date -Iseconds`, and the input verbatim under Original input. Run `python3 scripts/validate.py` and fix every error.

5. **Show the plan** in chat: name, date and time, audience, linked tasks (`T-NNNN title`), and the agenda as a list (`1. Title — P1`). Mention which earlier meetings of the series were used, if any. Don't show Original input. End with the file path.

## Protocol mode

P1. **Load** the meeting found in Which meeting, every other meeting with the same name (see Same-name meetings), its linked tasks, and the user's projects.

P2. **Write the protocol** in polished English, following the data model shape:
   - First line: `Held <date> · Attendees: <names>`, using the date and names from the notes. The date is the meeting's `date`. If no attendees are named, write `Attendees: not recorded`.
   - **Decisions**: what was agreed, each tied to its agenda item where possible.
   - **Action items**: `Owner — action — due YYYY-MM-DD` (leave out the due date if none was said). Write the user as `Me`. Keep other people's names exactly as written.
   - **Open points**: what was raised but not settled, plus P1 agenda items that weren't covered.
   - Never add decisions, owners or dates that the notes don't contain. If something important is ambiguous (who owns an action, what was decided), ask before saving.

P3. **Save**: set `status: done`, fill Protocol, update `tasks` with every task now linked, set `updated`, and append the notes verbatim to Original input. Run `python3 scripts/validate.py` and fix every error.

P4. **Propose task changes.** Only these:
   - **Update a linked task**: the notes say it is done, cancelled or started, or it got a new due date, week or priority.
   - **New task**: an action item owned by the user (`Me`) that matches no existing task. Also an item owned by someone else, if the user needs to follow up on it.
   Show the proposals as a numbered list (`1. T-0007 Review all Jira…: status → done`, `2. New: Send the forecast to Anna — P2, due 2026-10-12, project flow`). Then ask with AskUserQuestion: **Apply all** / **Let me choose** / **None**. With **Let me choose**, ask which numbers to apply.
   - Apply updates with `python3 scripts/update_task.py`, following the `/task` rules.
   - Create new tasks following the `/new-task` rules: source `text`; Original input quotes the action-item line from the user's notes. Then add the new IDs to the meeting's `tasks` and to their action items in the Protocol.
   - Run `python3 scripts/validate.py`.

P5. **Report**: the meeting's name, date and time, which earlier meetings of the series were used, the protocol as a compact list (decisions, action items, open points), the applied task changes, one per line as `T-NNNN — title: what changed`, and the file path.

## Rules

- Never invent numbers, names, decisions or facts about the user's business. Use only what the input, projects, tasks and earlier meetings say. Mark anything else as something to check (e.g. "Check: current Q4 win rate").
- When the user says a meeting was cancelled, set `status: cancelled` and `updated`; Protocol stays `None yet.`
