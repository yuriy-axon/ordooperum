#!/usr/bin/env python3
"""Validate data/ against docs/data-model.md.

Usage:
  python3 scripts/validate.py            check everything; exit 1 on errors
  python3 scripts/validate.py --next-id  print the next free task ID
  python3 scripts/validate.py --hook     PostToolUse hook: check only if a data/ file was edited; exit 2 on errors
"""
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
TASKS = DATA / "tasks"
PROJECTS = DATA / "projects"
MEETINGS = DATA / "meetings"
PROFILE = DATA / "profile.md"
PROFILE_FIELDS = ["location", "timezone", "currency", "updated"]

TIERS = {"business", "personal"}
PRIORITIES = {"P1", "P2", "P3", "P4", "P5"}
OPEN_STATUSES = {"new", "in-progress"}
CLOSED_STATUSES = {"done", "cancelled"}
TASK_STATUSES = OPEN_STATUSES | CLOSED_STATUSES
PROJECT_STATUSES = {"active", "archived"}
SOURCES = {"text", "audio"}

TASK_FIELDS = ["id", "title", "tier", "project", "priority", "status", "due", "week", "pinned", "created", "updated", "closed", "source"]
PROJECT_FIELDS = ["id", "name", "tier", "status", "created"]
TASK_SECTIONS = ["Description", "Additional information", "Original input"]
PROJECT_SECTIONS = ["Description", "Context"]
MEETING_FIELDS = ["id", "title", "audience", "date", "duration", "tier", "project", "status", "created", "updated"]
MEETING_SECTIONS = ["Goal", "Agenda", "Preparation", "Original brief"]
MEETING_STATUSES = {"planned", "done", "cancelled"}
AGENDA_ITEM = re.compile(r"^### \d+\. .+ — (P1|P2|P3)(?: · \d+ min)?$")

TASK_ID = re.compile(r"^T-\d{4}$")
ISO_WEEK = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def parse(path):
    """Return (frontmatter dict, body) or raise ValueError."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("unterminated frontmatter")
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep:
            raise ValueError(f"bad frontmatter line: {line!r}")
        meta[key.strip()] = value.strip()
    return meta, text[end + 5:]


def is_timestamp(value):
    try:
        return datetime.fromisoformat(value).tzinfo is not None
    except ValueError:
        return False


def check_fields(meta, required, errors, where):
    for field in required:
        if field not in meta or meta[field] == "":
            errors.append(f"{where}: missing field '{field}' (use null if unknown)")
    for field in meta:
        if field not in required:
            errors.append(f"{where}: unknown field '{field}'")


def check_sections(body, required, errors, where):
    found = re.findall(r"^## (.+?)\s*$", body, flags=re.M)
    if found != required:
        errors.append(f"{where}: sections must be {required}, found {found}")
    for name in required:
        m = re.search(rf"^## {re.escape(name)}\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S)
        if m and not m.group(1).strip():
            errors.append(f"{where}: section '{name}' is empty")


def load_projects(errors):
    projects = {}
    for tier in sorted(TIERS):
        for path in sorted((PROJECTS / tier).glob("*.md")):
            where = path.relative_to(ROOT)
            try:
                meta, body = parse(path)
            except ValueError as e:
                errors.append(f"{where}: {e}")
                continue
            check_fields(meta, PROJECT_FIELDS, errors, where)
            check_sections(body, PROJECT_SECTIONS, errors, where)
            pid = meta.get("id", "")
            if pid != path.stem:
                errors.append(f"{where}: id '{pid}' must match file name '{path.stem}'")
            if not SLUG.match(pid):
                errors.append(f"{where}: id must be a lowercase slug")
            if meta.get("tier") != tier:
                errors.append(f"{where}: tier '{meta.get('tier')}' must match folder '{tier}'")
            if meta.get("status") not in PROJECT_STATUSES:
                errors.append(f"{where}: status must be one of {sorted(PROJECT_STATUSES)}")
            if "created" in meta and not is_timestamp(meta["created"]):
                errors.append(f"{where}: created must be an ISO 8601 timestamp with time zone")
            if pid in projects:
                errors.append(f"{where}: duplicate project id '{pid}'")
            projects[pid] = tier
    return projects


def check_tasks(projects, errors):
    ids = {}
    for path in sorted(TASKS.glob("*.md")):
        where = path.relative_to(ROOT)
        try:
            meta, body = parse(path)
        except ValueError as e:
            errors.append(f"{where}: {e}")
            continue
        check_fields(meta, TASK_FIELDS, errors, where)
        check_sections(body, TASK_SECTIONS, errors, where)
        tid = meta.get("id", "")
        if not TASK_ID.match(tid):
            errors.append(f"{where}: id must look like T-0001")
        elif not (path.stem.startswith(tid + "-") and SLUG.match(path.stem[len(tid) + 1:])):
            errors.append(f"{where}: file name must be '{tid}-<lowercase-slug>.md'")
        if tid in ids:
            errors.append(f"{where}: duplicate id '{tid}' (also in {ids[tid]})")
        ids[tid] = where
        if len(meta.get("title", "")) > 60:
            errors.append(f"{where}: title longer than 60 characters")
        tier, project = meta.get("tier"), meta.get("project")
        if tier not in TIERS:
            errors.append(f"{where}: tier must be one of {sorted(TIERS)}")
        if project not in projects:
            errors.append(f"{where}: project '{project}' does not exist in data/projects/")
        elif projects[project] != tier:
            errors.append(f"{where}: tier '{tier}' does not match project's tier '{projects[project]}'")
        if meta.get("priority") not in PRIORITIES:
            errors.append(f"{where}: priority must be P1-P5")
        if meta.get("status") not in TASK_STATUSES:
            errors.append(f"{where}: status must be one of {sorted(TASK_STATUSES)}")
        if meta.get("source") not in SOURCES:
            errors.append(f"{where}: source must be one of {sorted(SOURCES)}")
        due = meta.get("due")
        if due and due != "null":
            try:
                date.fromisoformat(due)
            except ValueError:
                errors.append(f"{where}: due must be YYYY-MM-DD or null")
        week = meta.get("week")
        if week and week != "null" and not ISO_WEEK.match(week):
            errors.append(f"{where}: week must be YYYY-Www (e.g. 2026-W41) or null")
        pinned = meta.get("pinned")
        if pinned not in ("true", "false"):
            errors.append(f"{where}: pinned must be true or false")
        elif pinned == "true" and (not week or week == "null"):
            errors.append(f"{where}: a pinned task must have a week")
        closed = meta.get("closed")
        is_closed = meta.get("status") in CLOSED_STATUSES
        if is_closed and (not closed or closed == "null"):
            errors.append(f"{where}: closed must be set when status is {meta.get('status')}")
        elif not is_closed and closed and closed != "null":
            errors.append(f"{where}: closed must be null while the task is open")
        elif is_closed and not is_timestamp(closed):
            errors.append(f"{where}: closed must be an ISO 8601 timestamp with time zone")
        for field in ("created", "updated"):
            if field in meta and not is_timestamp(meta[field]):
                errors.append(f"{where}: {field} must be an ISO 8601 timestamp with time zone")
    return ids


def check_meetings(projects, errors):
    for path in sorted(MEETINGS.glob("*.md")):
        where = path.relative_to(ROOT)
        try:
            meta, body = parse(path)
        except ValueError as e:
            errors.append(f"{where}: {e}")
            continue
        check_fields(meta, MEETING_FIELDS, errors, where)
        check_sections(body, MEETING_SECTIONS, errors, where)
        if meta.get("id") != path.stem:
            errors.append(f"{where}: id must match the file name '{path.stem}'")
        if not re.match(r"^(\d{4}-\d{2}-\d{2}|undated)-[a-z0-9]+(-[a-z0-9]+)*$", path.stem):
            errors.append(f"{where}: file name must be '<YYYY-MM-DD or undated>-<slug>.md'")
        mdate = meta.get("date")
        if mdate != "null":
            try:
                date.fromisoformat(mdate or "")
            except ValueError:
                errors.append(f"{where}: date must be YYYY-MM-DD or null")
        if meta.get("duration") != "null" and not (meta.get("duration") or "").isdigit():
            errors.append(f"{where}: duration must be minutes (a number) or null")
        tier, project = meta.get("tier"), meta.get("project")
        if tier not in TIERS:
            errors.append(f"{where}: tier must be one of {sorted(TIERS)}")
        if project != "null":
            if project not in projects:
                errors.append(f"{where}: project '{project}' does not exist in data/projects/")
            elif projects[project] != tier:
                errors.append(f"{where}: tier '{tier}' does not match project's tier '{projects[project]}'")
        if meta.get("status") not in MEETING_STATUSES:
            errors.append(f"{where}: status must be one of {sorted(MEETING_STATUSES)}")
        for field in ("created", "updated"):
            if field in meta and not is_timestamp(meta[field]):
                errors.append(f"{where}: {field} must be an ISO 8601 timestamp with time zone")
        agenda = re.search(r"^## Agenda\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S)
        items = re.findall(r"^### .*$", agenda.group(1), flags=re.M) if agenda else []
        if agenda and not items:
            errors.append(f"{where}: Agenda needs at least one item ('### 1. Title — P1 · 10 min')")
        for item in items:
            if not AGENDA_ITEM.match(item):
                errors.append(f"{where}: agenda item must look like '### 1. Title — P1 · 10 min', found '{item}'")


def check_profile(errors):
    where = PROFILE.relative_to(ROOT)
    if not PROFILE.exists():
        errors.append(f"{where}: missing")
        return
    try:
        meta, body = parse(PROFILE)
    except ValueError as e:
        errors.append(f"{where}: {e}")
        return
    check_fields(meta, PROFILE_FIELDS, errors, where)
    check_sections(body, ["Context"], errors, where)
    if not re.match(r"^[A-Z]{3}$", meta.get("currency", "")):
        errors.append(f"{where}: currency must be a 3-letter code like EUR")
    if "updated" in meta and not is_timestamp(meta["updated"]):
        errors.append(f"{where}: updated must be an ISO 8601 timestamp with time zone")


def collect_errors():
    errors = []
    check_profile(errors)
    projects = load_projects(errors)
    check_tasks(projects, errors)
    check_meetings(projects, errors)
    return errors


def next_id():
    numbers = [int(m.group(1)) for p in TASKS.glob("T-*.md") if (m := re.match(r"T-(\d{4})", p.name))]
    return f"T-{max(numbers, default=0) + 1:04d}"


def main():
    args = sys.argv[1:]
    if "--next-id" in args:
        print(next_id())
        return 0
    if "--hook" in args:
        try:
            event = json.load(sys.stdin)
            edited = event.get("tool_input", {}).get("file_path", "")
        except (ValueError, AttributeError):
            edited = ""
        if not edited or not Path(edited).resolve().is_relative_to(DATA):
            return 0
    errors = collect_errors()
    if errors:
        print("Data validation failed:\n" + "\n".join(f"- {e}" for e in errors), file=sys.stderr)
        return 2 if "--hook" in args else 1
    if "--hook" not in args:
        print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
