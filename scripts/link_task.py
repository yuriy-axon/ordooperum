#!/usr/bin/env python3
"""Add or remove a link on a task. Used by the task agent and the web app.

Usage:
  python3 scripts/link_task.py T-0003 https://example.com/page          add a link
  python3 scripts/link_task.py T-0003 https://example.com/page --remove remove it

Links are kept in the task's Links section (created after Additional information when the first link
is added, removed with the last one), one '- <url>' bullet each, oldest first, without duplicates.
Sets `updated`. The whole data set is validated; on any error the file is restored.
"""
import re
import sys
from datetime import datetime
from urllib.parse import urlparse

from update_task import UpdateError, find_task
from validate import collect_errors

SECTION = re.compile(r"^## Links\s*\n(.*?)(?=^## )", flags=re.M | re.S)


def clean_url(url):
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or re.search(r"\s", url):
        raise UpdateError("A link must be a full web address starting with http:// or https://")
    return url


def change_link(task_id, url, remove=False):
    """Return True if the links changed."""
    url = clean_url(url)
    path = find_task(task_id)
    original = path.read_text(encoding="utf-8")
    m = SECTION.search(original)
    links = re.findall(r"^- (\S+)\s*$", m.group(1), flags=re.M) if m else []
    if remove:
        if url not in links:
            return False
        links.remove(url)
    else:
        if url in links:
            return False
        links.append(url)

    block = "## Links\n\n" + "".join(f"- {link}\n" for link in links) + "\n" if links else ""
    if m:
        body = original[:m.start()] + block + original[m.end():]
    else:
        body, n = re.subn(r"(?=^## (Comments|Original input)\s*$)", block, original, count=1, flags=re.M)
        if n != 1:
            raise UpdateError(f"Section 'Original input' missing in {path.name}")
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
    args = [a for a in sys.argv[1:] if a != "--remove"]
    if len(args) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    remove = "--remove" in sys.argv[1:]
    try:
        changed = change_link(args[0], args[1], remove)
    except UpdateError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    print(f"{args[0]}: link {'removed' if remove else 'added'}" if changed else f"{args[0]}: nothing to change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
