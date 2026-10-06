#!/usr/bin/env python3
"""Plan open tasks into weeks. The rules are described in .claude/skills/plan/SKILL.md.

Usage:
  python3 scripts/plan.py                 show what would change (nothing is written)
  python3 scripts/plan.py --apply         apply the plan
  python3 scripts/plan.py --pin T-0004=2026-W44 [--pin ...]   pin tasks to a week (with --apply to save)
  python3 scripts/plan.py --unpin T-0004  release a pin (with --apply to save)
  python3 scripts/plan.py --today 2026-10-11   pretend today is another date (for testing)

The target week is next week when run on a Sunday, otherwise the current week.
"""
import argparse
import re
import sys
from datetime import date, datetime, timedelta

from validate import ISO_WEEK, OPEN_STATUSES, TASKS, parse

PRIORITY_ORDER = ["P1", "P2", "P3", "P4", "P5"]
SPREAD = {"P3": 4, "P4": 13}  # number of weeks, starting at the target week, to spread over


def week_of(d):
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def shift(week, n):
    year, num = week.split("-W")
    return week_of(date.fromisocalendar(int(year), int(num), 1) + timedelta(weeks=n))


def label(week):
    return f"Week {int(week.split('-W')[1])}" if week else "—"


def null(v):
    return None if v in (None, "", "null") else v


def load_open_tasks():
    tasks = []
    for path in sorted(TASKS.glob("*.md")):
        meta, _ = parse(path)
        if meta.get("status") in OPEN_STATUSES:
            meta["path"] = path
            meta["week"] = null(meta.get("week"))
            meta["due"] = null(meta.get("due"))
            meta["pinned"] = meta.get("pinned") == "true"
            tasks.append(meta)
    return tasks


def plan(tasks, target, pins, unpins):
    """Return {task id: (new week, new pinned, reason)} for tasks that change."""
    changes = {}

    def set_week(t, week, pinned, reason):
        if (week, pinned) != (t["week"], t["pinned"]):
            changes[t["id"]] = (week, pinned, reason)
        t["week"], t["pinned"] = week, pinned

    by_id = {t["id"]: t for t in tasks}
    for tid in unpins:
        if tid in by_id:
            set_week(by_id[tid], by_id[tid]["week"], False, "Pin released by you")
    for tid, week in pins.items():
        if tid in by_id:
            set_week(by_id[tid], week, True, "Pinned by you")

    for t in tasks:
        due_week = week_of(date.fromisoformat(t["due"])) if t["due"] else None
        if t["priority"] == "P1":
            set_week(t, target, True, "Critical: always pinned to the planning week")
        elif t["week"] and t["week"] < target:
            set_week(t, target, t["pinned"], f"Not done in {label(t['week'])}, moved forward")
        elif t["pinned"]:
            continue
        elif due_week and due_week <= target and t["week"] != target:
            set_week(t, target, False, f"Due {t['due']}")

    load = {}
    for t in tasks:
        if t["week"]:
            load[t["week"]] = load.get(t["week"], 0) + 1

    unplanned = [t for t in tasks if not t["week"]]
    unplanned.sort(key=lambda t: (PRIORITY_ORDER.index(t["priority"]), t["due"] or "9999", t["id"]))
    for t in unplanned:
        due_week = week_of(date.fromisoformat(t["due"])) if t["due"] else None
        p = t["priority"]
        if p == "P2":
            week, reason = target, "High priority"
        elif p in SPREAD:
            weeks = [shift(target, i) for i in range(SPREAD[p])]
            if due_week:
                weeks = [w for w in weeks if w <= due_week] or [target]
            week = min(weeks, key=lambda w: (load.get(w, 0), w))
            reason = f"{p}: least busy week{' before the due date' if due_week else ''}"
        elif due_week:  # P5 with a due date
            week, reason = max(due_week, target), f"Due {t['due']}"
        else:
            continue  # P5 without a due date stays unplanned
        if due_week and week > due_week:
            week = max(due_week, target)
        load[week] = load.get(week, 0) + 1
        set_week(t, week, False, reason)
    return changes


def write(t, week, pinned, now):
    text = t["path"].read_text(encoding="utf-8")
    for field, value in (("week", week or "null"), ("pinned", "true" if pinned else "false"), ("updated", now)):
        text, n = re.subn(rf"^{field}: .*$", f"{field}: {value}", text, count=1, flags=re.M)
        if n != 1:
            raise SystemExit(f"{t['path'].name}: field '{field}' not found")
    t["path"].write_text(text, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--pin", action="append", default=[], metavar="T-NNNN=YYYY-Www")
    ap.add_argument("--unpin", action="append", default=[], metavar="T-NNNN")
    ap.add_argument("--today", type=date.fromisoformat, default=date.today())
    args = ap.parse_args()

    today = args.today
    target = week_of(today + timedelta(days=1)) if today.isoweekday() == 7 else week_of(today)

    pins = {}
    for item in args.pin:
        tid, _, week = item.partition("=")
        if not ISO_WEEK.match(week):
            raise SystemExit(f"Bad pin '{item}': use T-0004=2026-W44")
        if week < week_of(today):
            raise SystemExit(f"Can't pin {tid} to {label(week)}: that week is already over")
        pins[tid] = week

    tasks = load_open_tasks()
    known = {t["id"] for t in tasks}
    for tid in list(pins) + args.unpin:
        if tid not in known:
            raise SystemExit(f"{tid} is not an open task")

    changes = plan(tasks, target, pins, args.unpin)
    by_id = {t["id"]: t for t in tasks}

    print(f"Planning {label(target)} ({target}), today {today.isoformat()}.\n")
    if not changes:
        print("Nothing to change.")
    else:
        print("| ID | Priority | Title | Week | Reason |")
        print("|----|----------|-------|------|--------|")
        for tid, (week, pinned, reason) in sorted(changes.items()):
            t = by_id[tid]
            pin = " 📌" if pinned else ""
            print(f"| {tid} | {t['priority']} | {t['title']} | {label(week)}{pin} | {reason} |")
    in_target = sorted((t for t in tasks if t["week"] == target),
                       key=lambda t: (PRIORITY_ORDER.index(t["priority"]), t["id"]))
    print(f"\n{label(target)} has {len(in_target)} task{'s' if len(in_target) != 1 else ''}.")
    unplanned = [t for t in tasks if not t["week"]]
    if unplanned:
        print(f"{len(unplanned)} open task{'s' if len(unplanned) != 1 else ''} left unplanned (P5 without a due date).")

    if args.apply and changes:
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        for tid, (week, pinned, _) in changes.items():
            write(by_id[tid], week, pinned, now)
        print("\nSaved.")
    elif changes:
        print("\nDry run: nothing saved. Add --apply to save.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
