#!/usr/bin/env python3
"""Add a comment to a task. Used by the task agent and the web app.

Usage:
  python3 scripts/comment_task.py T-0003 "Called the bank; they need the new contract first."

Appends a '### YYYY-MM-DD HH:MM' entry to the task's Comments section (creating the section before
Original input if needed) and sets `updated`. The text is kept as written; lines starting with '#'
get a leading space so they can't break the file's sections. The whole data set is validated;
on any error the file is restored.
"""
import re
import sys
from datetime import datetime

from update_task import UpdateError, find_task
from validate import collect_errors


def add_comment(task_id, text):
    """Return the header of the new comment, e.g. '2026-10-26 10:31'."""
    text = "\n".join((" " + line if line.startswith("#") else line.rstrip()) for line in (text or "").strip().splitlines())
    if not text.strip():
        raise UpdateError("A comment can't be empty")
    path = find_task(task_id)
    original = path.read_text(encoding="utf-8")
    now = datetime.now().astimezone()
    stamp = now.strftime("%Y-%m-%d %H:%M")
    entry = f"### {stamp}\n\n{text}\n\n"

    body = original
    if re.search(r"^## Comments\s*$", body, flags=re.M):
        body, n = re.subn(r"\n*(?=^## Original input\s*$)", "\n\n" + entry, body, count=1, flags=re.M)
    else:
        body, n = re.subn(r"\n*(?=^## Original input\s*$)", "\n\n## Comments\n\n" + entry, body, count=1, flags=re.M)
    if n != 1:
        raise UpdateError(f"Section 'Original input' missing in {path.name}")
    body, n = re.subn(r"^updated: .*$", f"updated: {now.isoformat(timespec='seconds')}", body, count=1, flags=re.M)
    if n != 1:
        raise UpdateError(f"Field 'updated' missing in {path.name}")
    path.write_text(body, encoding="utf-8")

    errors = [e for e in collect_errors() if path.name in e]
    if errors:
        path.write_text(original, encoding="utf-8")
        raise UpdateError("; ".join(errors))
    return stamp


def main():
    if len(sys.argv) != 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    try:
        stamp = add_comment(sys.argv[1], sys.argv[2])
    except UpdateError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"{sys.argv[1]}: comment added ({stamp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
