#!/usr/bin/env python3
"""Print tasks as a Markdown table.

Usage:
  python3 scripts/list_tasks.py [open|closed|all]   default: open

Sorted by priority, then due date (none last), then ID.
"""
import sys
from datetime import date

from validate import OPEN_STATUSES, CLOSED_STATUSES, PROJECTS, TASKS, parse

FILTERS = {"open": OPEN_STATUSES, "closed": CLOSED_STATUSES, "all": OPEN_STATUSES | CLOSED_STATUSES}


def project_names():
    names = {}
    for path in PROJECTS.glob("*/*.md"):
        try:
            meta, _ = parse(path)
        except ValueError:
            continue
        names[meta.get("id")] = meta.get("name", meta.get("id"))
    return names


def cell(value):
    return str(value).replace("|", "\\|")


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "open").strip().lower() or "open"
    if arg not in FILTERS:
        print(f"Unknown filter '{arg}'. Use one of: open, closed, all.", file=sys.stderr)
        return 1

    names = project_names()
    today = date.today().isoformat()
    rows, broken = [], []
    for path in TASKS.glob("*.md"):
        try:
            meta, _ = parse(path)
        except ValueError:
            broken.append(path.name)
            continue
        if meta.get("status") in FILTERS[arg]:
            rows.append(meta)

    def key(t):
        due = t.get("due")
        due = None if due in (None, "", "null") else due
        return (t.get("priority", "P9"), due is None, due or "", t.get("id", ""))

    rows.sort(key=key)

    if not rows:
        print(f"No {arg} tasks.")
    else:
        print("| ID | Priority | Title | Project | Due | Status |")
        print("|----|----------|-------|---------|-----|--------|")
        for t in rows:
            priority = t.get("priority", "")
            if priority == "P1":
                priority = "🔴 P1"
            due = t.get("due", "null")
            if due == "null":
                due = "—"
            elif due < today and t.get("status") in OPEN_STATUSES:
                due = f"**{due} (overdue)**"
            project = f"{names.get(t.get('project'), t.get('project'))} ({t.get('tier')})"
            print(f"| {t.get('id')} | {priority} | {cell(t.get('title', ''))} | {cell(project)} | {due} | {t.get('status')} |")
        label = "" if arg == "all" else f" {arg}"
        print(f"\n{len(rows)}{label} task{'s' if len(rows) != 1 else ''}.")
    if broken:
        print(f"\nCould not read: {', '.join(sorted(broken))}. Run `python3 scripts/validate.py`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
