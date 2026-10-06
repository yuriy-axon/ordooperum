---
name: plan
description: Plan open tasks into weeks. Moves unfinished tasks forward, puts every critical task into the planning week, respects tasks the user pinned to a week, and spreads the rest by priority and due date. Runs automatically every Sunday; also on /plan, or when the user asks to plan, schedule or pin tasks to weeks.
argument-hint: "[pin T-0004 to week 44]"
---

# Plan

Assign each open task to a week by setting its `week`. The rules are implemented in `scripts/plan.py`; run it, don't plan by hand.

## Rules

The **planning week** is next week when run on a Sunday, otherwise the current week.

1. Closed tasks (done or cancelled) are never touched.
2. Every `P1` goes into the planning week and is pinned there, no matter what was planned before.
3. An open task whose week is over moves to the planning week; a pinned task stays pinned.
4. Any other task the user pinned to a week stays there.
5. A task due in or before the planning week goes into the planning week.
6. Unplanned tasks, highest priority first:
   - `P2` → the planning week
   - `P3` → the least busy of the next 4 weeks
   - `P4` → the least busy of the next 13 weeks
   - `P5` → stays unplanned unless it has a due date
   - never later than the week of the due date
7. No limit on tasks per week.

## Steps

1. If the user asked to pin tasks ("T-0004 to week 44", "put the bank task in next week"), resolve each task ID (by matching titles in `data/tasks/` if needed; ask if ambiguous) and the ISO week (`YYYY-Www`; get the current week from `date +%G-W%V`). Use `--pin T-NNNN=YYYY-Www`; to release a pin, `--unpin T-NNNN`.
2. Run `python3 scripts/plan.py --apply [--pin …] [--unpin …]`. Planning is applied without asking for confirmation.
3. Run `python3 scripts/validate.py`.
4. Report the script's table and summary as printed.
