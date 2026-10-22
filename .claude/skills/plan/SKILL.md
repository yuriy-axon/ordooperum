---
name: plan
description: Plan open tasks into weeks. Moves unfinished tasks forward, carries in-progress tasks into the next week, puts every critical task into the planning week, respects tasks the user pinned to a week, and spreads the rest by priority and due date. Runs automatically every Sunday; also on /plan, or when the user asks to plan, schedule or pin tasks to weeks.
argument-hint: "[pin T-0004 to week 44]"
---

# Plan

Assign each open task to a week by setting its `week`. The rules are implemented in `scripts/plan.py`; run it, don't plan by hand.

## Rules

The **planning week** is next week when run on a Sunday, otherwise the current week.

1. Closed tasks (done or cancelled) are never touched.
2. Every `in-progress` task (one the user works on through the whole week) goes into the planning week and is pinned there, so it continues automatically into the next week until it is done.
3. Every `P1` goes into the planning week and is pinned there, no matter what was planned before.
4. An open task whose week is over moves to the planning week; a pinned task stays pinned.
5. Any other task the user pinned to a week stays there.
6. A task due in or before the planning week goes into the planning week.
7. Unplanned tasks, highest priority first:
   - `P2` → the planning week
   - `P3` → the least busy of the next 4 weeks
   - `P4` → the least busy of the next 13 weeks
   - never later than the week of the due date
8. Weekly series (`repeat: weekly`) are never planned themselves. For each one, the script creates its separate instance for the planning week (unless it exists already), and closes a series as `done` once its `repeat_until` is over. Instances are pinned to their own week and are never moved or carried over: an unfinished one stays in its week as not done, because the next week has its own instance.
9. No limit on tasks per week.
10. Every new week a task gets is appended to its `weeks` history, so repeatedly carried-over tasks stay visible.

## Steps

1. If the user asked to pin tasks ("T-0004 to week 44", "put the bank task in next week"), resolve each task ID (by matching titles in `data/tasks/` if needed; ask if ambiguous) and the ISO week (`YYYY-Www`; get the current week from `date +%G-W%V`). Use `--pin T-NNNN=YYYY-Www`; to release a pin, `--unpin T-NNNN`.
2. Run `python3 scripts/plan.py --apply [--pin …] [--unpin …]`. Planning is applied without asking for confirmation.
3. Run `python3 scripts/validate.py`.
4. Report the script's table and summary as printed.
