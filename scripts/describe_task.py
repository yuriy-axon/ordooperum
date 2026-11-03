#!/usr/bin/env python3
"""Replace the Description of a task. Used by the web app's description editor.

Usage:
  python3 scripts/describe_task.py T-0003 "Approve every ICO procedure before the audit."

Replaces the text of the task's Description section and sets `updated`. The text is kept as
written; lines starting with '#' get a leading space so they can't break the file's sections.
Original input is never touched. The whole data set is validated; on any error the file is restored.
"""
import re
import sys
from datetime import datetime

from update_task import UpdateError, find_task
from validate import collect_errors


def set_description(task_id, text):
    """Return True if the description changed."""
    text = "\n".join((" " + line if line.startswith("#") else line.rstrip()) for line in (text or "").strip().splitlines())
    if not text.strip():
        raise UpdateError("The description can't be empty")
    path = find_task(task_id)
    original = path.read_text(encoding="utf-8")
    m = re.search(r"^## Description\s*\n(.*?)(?=^## )", original, flags=re.M | re.S)
    if not m:
        raise UpdateError(f"Section 'Description' missing in {path.name}")
    if m.group(1).strip() == text.strip():
        return False
    body = original[:m.start()] + "## Description\n\n" + text + "\n\n" + original[m.end():]
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    body, n = re.subn(r"^updated: .*$", f"updated: {now}", body, count=1, flags=re.M)
    if n != 1:
        raise UpdateError(f"Field 'updated' missing in {path.name}")
    path.write_text(body, encoding="utf-8")

    errors = [e for e in collect_errors() if path.name in e]
    if errors:
        path.write_text(original, encoding="utf-8")
        raise UpdateError("; ".join(errors))
    return True


def main():
    if len(sys.argv) != 3:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    try:
        changed = set_description(sys.argv[1], sys.argv[2])
    except UpdateError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"{sys.argv[1]}: description {'updated' if changed else 'unchanged'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
