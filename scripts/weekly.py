#!/usr/bin/env python3
"""Create the instance of a weekly series for one week. See "Weekly tasks" in docs/data-model.md.

Usage:
  python3 scripts/weekly.py T-0013                  instance for the current week
  python3 scripts/weekly.py T-0013 --week 2026-W45  instance for that week

Prints the instance's ID and file. If the instance already exists, prints it and creates nothing.
Refuses weeks before the series started or after its repeat_until, and closed series.
"""
import argparse
import re
import subprocess
import sys
from datetime import date, datetime

from validate import CLOSED_STATUSES, ISO_WEEK, ROOT, TASKS, collect_errors, next_id, parse, parse_weeks


class WeeklyError(Exception):
    pass


def week_of(d):
    year, week, _ = d.isocalendar()
    return f"{year}-W{week:02d}"


def find_series(series_id):
    matches = list(TASKS.glob(f"{series_id}-*.md"))
    if len(matches) != 1:
        raise WeeklyError(f"Task {series_id} not found")
    meta, body = parse(matches[0])
    if meta.get("repeat") != "weekly":
        raise WeeklyError(f"{series_id} is not a weekly series")
    return matches[0], meta, body


def find_instance(series_id, week):
    """An instance belongs to the week it was created for (the first entry of `weeks`); it is never moved."""
    for path in sorted(TASKS.glob("*.md")):
        meta, _ = parse(path)
        if meta.get("series") == series_id and (parse_weeks(meta.get("weeks")) or [None])[0] == week:
            return path, meta
    return None


def create_instance(series_id, week):
    """Return (id, path, created) for the instance of `series_id` in `week`."""
    if not ISO_WEEK.match(week):
        raise WeeklyError("Week must be YYYY-Www")
    path, meta, body = find_series(series_id)
    existing = find_instance(series_id, week)
    if existing:
        return existing[1]["id"], existing[0], False
    if meta.get("status") in CLOSED_STATUSES:
        raise WeeklyError(f"Series {series_id} has ended")
    start = week_of(datetime.fromisoformat(meta["created"]).date())
    last = week_of(date.fromisoformat(meta["repeat_until"]))
    if not start <= week <= last:
        raise WeeklyError(f"{series_id} repeats from {start} to {last}; {week} is outside that")

    description = re.search(r"^## Description\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S).group(1).strip()
    year, num = week.split("-W")
    tid = next_id()
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    suffix = f" · Week {int(num)}"
    base = meta["title"] if len(meta["title"]) + len(suffix) <= 60 else meta["title"][:59 - len(suffix)].rstrip() + "…"
    title = base + suffix
    slug = path.stem[len(series_id) + 1:]
    out = TASKS / f"{tid}-{slug}-{year}-w{num}.md"
    out.write_text(f"""---
id: {tid}
title: {title}
tier: {meta['tier']}
project: {meta['project']}
priority: {meta['priority']}
status: new
due: null
week: {week}
pinned: true
weeks: [{week}]
repeat: null
repeat_until: null
series: {series_id}
created: {now}
updated: {now}
closed: null
source: {meta['source']}
---

## Description

{description}

This is the instance for week {int(num)} of {year}.

## Additional information

None.

## Original input

> Created from weekly series {series_id} for {week}.
""", encoding="utf-8")
    errors = [e for e in collect_errors() if out.name in e]
    if errors:
        out.unlink()
        raise WeeklyError("; ".join(errors))
    return tid, out, True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series_id")
    ap.add_argument("--week", default=week_of(date.today()))
    args = ap.parse_args()
    try:
        tid, path, created = create_instance(args.series_id, args.week)
    except WeeklyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"{tid} {'created' if created else 'already exists'}: {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
