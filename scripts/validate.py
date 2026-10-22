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
PRIORITIES = {"P1", "P2", "P3", "P4"}
OPEN_STATUSES = {"new", "in-progress"}
CLOSED_STATUSES = {"done", "cancelled"}
TASK_STATUSES = OPEN_STATUSES | CLOSED_STATUSES
PROJECT_STATUSES = {"active", "archived"}
SOURCES = {"text", "audio"}
REPEATS = {"weekly", "null"}

TASK_FIELDS = ["id", "title", "tier", "project", "priority", "status", "due", "week", "pinned", "weeks", "repeat", "repeat_until",
              "series", "created", "updated", "closed", "source"]
PROJECT_FIELDS = ["id", "name", "tier", "status", "created"]
TASK_SECTIONS = ["Description", "Additional information", "Original input"]
PROJECT_SECTIONS = ["Description", "Context"]
MEETING_FIELDS = ["id", "name", "title", "audience", "date", "time", "duration", "tier", "project", "tasks", "status", "created", "updated"]
MEETING_SECTIONS = ["Goal", "Agenda", "Preparation", "Protocol", "Original input"]
PROTOCOL_PARTS = ["Decisions", "Action items", "Open points"]
MEETING_STATUSES = {"planned", "done", "cancelled"}
AGENDA_ITEM = re.compile(r"^### \d+\. .+ — (P1|P2|P3)(?: · \d+ min)?$")

TASK_ID = re.compile(r"^T-\d{4}$")
ISO_WEEK = re.compile(r"^\d{4}-W(0[1-9]|[1-4]\d|5[0-3])$")
SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
TIME = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def parse_list(value, item):
    """'[a, b]' -> ['a', 'b'] if every entry matches the `item` regex; None if malformed."""
    if not (value or "").startswith("[") or not value.endswith("]"):
        return None
    items = [w.strip() for w in value[1:-1].split(",") if w.strip()]
    return items if all(item.match(w) for w in items) else None


def parse_weeks(value):
    """'[2026-W40, 2026-W41]' -> ['2026-W40', '2026-W41']; None if malformed."""
    return parse_list(value, ISO_WEEK)


def format_weeks(weeks):
    return "[" + ", ".join(weeks) + "]"


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
    instances = []  # (file, series ID, week) of weekly instances
    repeating = set()
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
            errors.append(f"{where}: priority must be P1-P4")
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
        weeks = parse_weeks(meta.get("weeks"))
        if weeks is None:
            errors.append(f"{where}: weeks must be a list like [2026-W40, 2026-W41] or []")
        elif any(a == b for a, b in zip(weeks, weeks[1:])):
            errors.append(f"{where}: weeks must not repeat the same week twice in a row")
        elif week and week != "null" and (not weeks or weeks[-1] != week):
            errors.append(f"{where}: the last entry of weeks must equal week ({week})")
        repeat, until = meta.get("repeat"), meta.get("repeat_until")
        if repeat == "weekly":
            repeating.add(tid)
        if repeat not in REPEATS:
            errors.append(f"{where}: repeat must be one of {sorted(REPEATS)}")
        series = meta.get("series")
        if repeat == "weekly":
            try:
                date.fromisoformat(until or "")
            except ValueError:
                errors.append(f"{where}: repeat_until must be YYYY-MM-DD for a weekly series")
            if (week, pinned, meta.get("weeks"), due, series) != ("null", "false", "[]", "null", "null"):
                errors.append(f"{where}: a weekly series must have week: null, pinned: false, weeks: [], due: null, series: null")
        elif until != "null":
            errors.append(f"{where}: repeat_until must be null when repeat is null")
        if series != "null":
            if not TASK_ID.match(series or ""):
                errors.append(f"{where}: series must be a task ID like T-0013 or null")
            elif not week or week == "null" or not weeks:
                errors.append(f"{where}: a weekly instance must have a week")
            elif weeks != [week] or pinned != "true":
                errors.append(f"{where}: a weekly instance is never carried over: it must have pinned: true and weeks: [{week}]")
            else:
                instances.append((where, series, weeks[0]))  # the week it was created for
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
    seen = {}
    for where, series, week in instances:
        if series not in repeating:
            errors.append(f"{where}: series {series} is not an existing weekly series")
        if (series, week) in seen:
            errors.append(f"{where}: {series} already has an instance for {week} ({seen[(series, week)]})")
        seen[(series, week)] = where
    return ids


def check_meetings(projects, task_ids, errors):
    seen = {}
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
        name, mdate, mtime = meta.get("name") or "null", meta.get("date"), meta.get("time")
        if name == "null" or not slugify(name):
            errors.append(f"{where}: name is required")
        try:
            date.fromisoformat(mdate or "")
        except ValueError:
            errors.append(f"{where}: date is required, as YYYY-MM-DD")
        if mtime != "null" and not TIME.match(mtime or ""):
            errors.append(f"{where}: time must be HH:MM (24-hour) or null")
        short = f"{mdate}-{slugify(name)}"
        timed = f"{mdate}-{(mtime or '').replace(':', '')}-{slugify(name)}" if TIME.match(mtime or "") else None
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", mdate or "") and path.stem not in (short, timed):
            errors.append(f"{where}: file name must be '{short}.md'" + (f" (or '{timed}.md')" if timed else ""))
        key = (mdate, slugify(name), mtime)
        if key in seen:
            errors.append(f"{where}: same date, name and time as {seen[key]}; add to that meeting instead")
        seen[key] = where
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
        linked = parse_list(meta.get("tasks"), TASK_ID)
        if linked is None:
            errors.append(f"{where}: tasks must be a list like [T-0002, T-0006] or []")
        else:
            for tid in linked:
                if tid not in task_ids:
                    errors.append(f"{where}: linked task {tid} does not exist")
            text = re.split(r"^## Original input\s*$", body, flags=re.M)[0]
            for tid in sorted(set(re.findall(r"\bT-\d{4}\b", text)) - set(linked)):
                errors.append(f"{where}: {tid} is mentioned but missing from tasks")
        protocol = re.search(r"^## Protocol\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S)
        protocol = protocol.group(1).strip() if protocol else ""
        if meta.get("status") == "planned" and protocol and protocol != "None yet.":
            errors.append(f"{where}: Protocol must be 'None yet.' while the meeting is planned")
        if meta.get("status") == "done":
            parts = re.findall(r"^### (.+?)\s*$", protocol, flags=re.M)
            if parts != PROTOCOL_PARTS:
                errors.append(f"{where}: Protocol of a done meeting needs subsections {PROTOCOL_PARTS}, found {parts}")
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
    task_ids = check_tasks(projects, errors)
    check_meetings(projects, task_ids, errors)
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
