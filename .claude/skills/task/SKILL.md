---
name: task
description: Maintain existing tasks — end (done), cancel, reopen, start, change priority, due date, week, project, title or description. Use when the user runs /task, or says a task is done/finished/ended/cancelled, or asks to change, move, reprioritize or edit a task.
argument-hint: "<what to change, e.g. T-0002 done>"
---

# Task

Apply the user's changes to existing tasks. Formats are in `docs/data-model.md`. This skill never creates tasks (that's `/new-task`) and never deletes them.

## Steps

1. **Find the task(s).** By ID if given; otherwise match the user's words against titles of tasks in `data/tasks/`. If more than one task could match, or none does, ask with AskUserQuestion (options: the closest 2–4 tasks as `T-NNNN — title`). Never guess.

2. **Map the request to changes:**
   - "done", "finished", "ended", "closed", "completed" → `status done`
   - "cancel", "drop", "won't do", "not needed" → `status cancelled`
   - "reopen", "not done after all" → `status new`
   - "started", "working on it" → `status in-progress`
   - priority words → `P1`–`P5` per the data model ("critical/urgent" P1 … "someday" P5)
   - a date → `due`; "no deadline" → `due null`
   - "this week", "next week", "week 44" → `week` (this pins it: planning won't move it); "unplan" → `week null`
   - a project name → `project` (must exist; if not, ask whether to create it via `/new-task` rules)
   If a requested change is unclear, ask. Don't infer changes the user didn't ask for.

3. **Apply structured changes** with
   `python3 scripts/update_task.py <ID> [--status …] [--priority …] [--due …] [--week …] [--project …]`
   It sets `closed` and `updated`, pins weeks, and validates. If it reports an error, tell the user and ask how to proceed.

4. **Text changes** (title, description): edit the file directly, in polished English per the data model, and set `updated` from `date -Iseconds`. Never edit Original input. Then run `python3 scripts/validate.py`.

5. **Report** one line per task: `T-NNNN — title: what changed`.
