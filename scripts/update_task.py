#!/usr/bin/env python3
"""Change the structured fields of one task. Used by the task agent and the web app.

Usage:
  python3 scripts/update_task.py T-0002 [--status done] [--priority P2] [--due 2026-10-20|null]
                                        [--week 2026-W44|null] [--project bank]
                                        [--repeat-until 2027-10-16]

- status done/cancelled sets `closed`; reopening (new/in-progress) clears it.
- Setting a week pins the task there (planning won't move it) and appends it to `weeks`;
  --week null unplans and unpins it (the `weeks` history is kept).
- --project also sets the tier to the project's tier.
- Weekly series (repeat: weekly): --repeat-until shortens or extends it; --status cancelled ends it.
  A series is never planned: --week and --due are refused. A weekly instance keeps its week: --week is refused.
- `updated` is always set. The whole data set is validated; on any error the file is restored.
"""
import argparse
import re
import sys
from datetime import date, datetime

from validate import (CLOSED_STATUSES, ISO_WEEK, PRIORITIES, PROJECTS, TASK_STATUSES, TASKS, collect_errors,
                      format_weeks, parse, parse_weeks)


class UpdateError(Exception):
    pass


def find_task(task_id):
    matches = list(TASKS.glob(f"{task_id}-*.md"))
    if len(matches) != 1:
        raise UpdateError(f"Task {task_id} not found")
    return matches[0]


def update(task_id, status=None, priority=None, due=None, week=None, project=None, repeat_until=None):
    """Apply changes; values of None mean 'leave as is', the string 'null' clears due/week.
    Returns the changed fields as {field: (old, new)}."""
    path = find_task(task_id)
    original = path.read_text(encoding="utf-8")
    meta, _ = parse(path)
    new = {}

    is_series = meta.get("repeat") == "weekly"
    if is_series and (week is not None or due is not None):
        raise UpdateError("A weekly series is never planned; change its weekly instances instead")
    if meta.get("series", "null") != "null" and week is not None and week != meta.get("week"):
        raise UpdateError("A weekly instance always stays in its own week; the other weeks have their own instances")
    if repeat_until is not None:
        if not is_series:
            raise UpdateError("Only a weekly series has an end date")
        try:
            date.fromisoformat(repeat_until)
        except ValueError:
            raise UpdateError("Repeat until must be YYYY-MM-DD")
        new["repeat_until"] = repeat_until

    if status is not None:
        if status not in TASK_STATUSES:
            raise UpdateError(f"Status must be one of {sorted(TASK_STATUSES)}")
        new["status"] = status
        was_closed = meta.get("status") in CLOSED_STATUSES
        if status in CLOSED_STATUSES and not was_closed:
            new["closed"] = datetime.now().astimezone().isoformat(timespec="seconds")
        elif status not in CLOSED_STATUSES:
            new["closed"] = "null"
    if priority is not None:
        if priority not in PRIORITIES:
            raise UpdateError("Priority must be P1-P4")
        new["priority"] = priority
    if due is not None:
        if due != "null":
            try:
                date.fromisoformat(due)
            except ValueError:
                raise UpdateError("Due must be YYYY-MM-DD or null")
        new["due"] = due
    if week is not None:
        if week != "null" and not ISO_WEEK.match(week):
            raise UpdateError("Week must be YYYY-Www or null")
        new["week"] = week
        new["pinned"] = "false" if week == "null" else "true"
        history = parse_weeks(meta.get("weeks")) or []
        if week != "null" and history[-1:] != [week]:
            new["weeks"] = format_weeks(history + [week])
    if project is not None:
        matches = list(PROJECTS.glob(f"*/{project}.md"))
        if len(matches) != 1:
            raise UpdateError(f"Project '{project}' not found")
        new["project"] = project
        new["tier"] = matches[0].parent.name

    changes = {k: (meta.get(k), v) for k, v in new.items() if meta.get(k) != v}
    if not changes:
        return {}
    changes["updated"] = (meta.get("updated"), datetime.now().astimezone().isoformat(timespec="seconds"))

    text = original
    for field, (_, value) in changes.items():
        text, n = re.subn(rf"^{field}: .*$", f"{field}: {value}", text, count=1, flags=re.M)
        if n != 1:
            raise UpdateError(f"Field '{field}' missing in {path.name}")
    path.write_text(text, encoding="utf-8")

    errors = [e for e in collect_errors() if path.name in e]
    if errors:
        path.write_text(original, encoding="utf-8")
        raise UpdateError("; ".join(errors))
    return changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("task_id")
    for field in ("status", "priority", "due", "week", "project", "repeat-until"):
        ap.add_argument(f"--{field}")
    args = ap.parse_args()
    try:
        changes = update(args.task_id, args.status, args.priority, args.due, args.week, args.project,
                         args.repeat_until)
    except UpdateError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if not changes:
        print(f"{args.task_id}: nothing to change.")
    for field, (old, new) in changes.items():
        if field not in ("updated", "weeks"):
            print(f"{args.task_id}: {field} {old} → {new}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
