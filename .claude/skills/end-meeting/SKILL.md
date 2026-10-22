---
name: end-meeting
description: Finish a meeting planned with /ordo. Goes through the meeting's talking points one by one, asks the user for notes on each, writes the final meeting notes (protocol) into the meeting file, and proposes tasks for the user's week from the action items. Use when the user runs /end-meeting, or says a meeting is over, finished or ended and wants to record it point by point.
argument-hint: "[meeting name or date — default: today's meeting]"
---

# End meeting

Turn a planned meeting into its final notes, point by point, so the outcome can feed the user's tasks for the week. Formats are in `docs/data-model.md` (Meetings, Tasks); the protocol rules are those of `/ordo` Protocol mode (`.claude/skills/ordo/SKILL.md`, steps P2–P5), which this skill follows.

## Steps

1. **Find the meeting.** Read `data/meetings/`. Use the name or date in the argument; with none, take today's `planned` meetings (date from `date -Iseconds`).
   - Exactly one match → use it.
   - Several → ask with AskUserQuestion (options: `<name> — <date> <time>`).
   - None → say there is no planned meeting for that, list the latest 3 planned ones, and ask which. If the user wants to record a meeting that was never planned, use `/ordo` instead.

2. **Collect notes, one point at a time.** Read the meeting's Agenda. For each talking point, in order, ask in chat and wait for the answer:

   > **Point 2 of 3 · ICO certification (P1).** What was said or decided? Who does what, and by when? (Reply `skip` if it wasn't discussed.)

   - Accept any language and any form (typed or dictated). Don't rewrite or judge the answer while collecting; only ask a short follow-up if an action item has no owner ("Who will do this?").
   - `skip` → the point wasn't covered.
   - After the last point, ask once: **Anything else discussed? And who attended?** (`no` is fine).

3. **Write the final notes** into the meeting's Protocol, following the data model shape and the `/ordo` rules (P2):
   - `Held <date> · Attendees: <names>` (or `Attendees: not recorded`).
   - **Decisions**, **Action items** (`Owner — action — due YYYY-MM-DD`; the user is `Me`), **Open points**. Tie each line to its talking point, e.g. `(point 2)`. A skipped P1 point goes to Open points as not covered.
   - Only what the user's notes say: never add decisions, owners or dates.
   - Set `status: done`, set `updated`, link every task mentioned in `tasks`, and append the notes verbatim to Original input, one line per point: `> 2. ICO certification: <the user's words>`.
   - Run `python3 scripts/validate.py` and fix every error.

4. **Propose tasks for the week** (as `/ordo` step P4), as a numbered list:
   - Each action item owned by `Me` that matches no existing task → **New task**: title, priority (from the talking point's priority: `P1`→P1, `P2`→P2, `P3`→P3, unless the notes say otherwise), due date if one was said, project and tier from the meeting (ask if the meeting has no project and it isn't obvious), and `week` = the current week (next week if today is Sunday), pinned.
   - Action items of other people the user must follow up on → **New task** "Follow up with <name> on <topic>".
   - Linked tasks the notes say are done, cancelled, started or moved → **Update**.
   Ask with AskUserQuestion: **Apply all** / **Let me choose** / **None**. Apply updates with `python3 scripts/update_task.py`; create tasks with the `/new-task` rules (`source: text`, Original input quotes the user's note for that point), then add their IDs to the meeting's `tasks` and to their action items in the Protocol. Run `python3 scripts/validate.py`.

5. **Report**: the meeting name and date, the final notes as a compact list (decisions, action items, open points), the tasks created or changed (`T-NNNN — title: what changed`), and the file path.
