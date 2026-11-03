#!/usr/bin/env python3
"""Local web app: serves the task board and a read-only JSON API over data/.

Usage:
  python3 apps/web/server.py [--port 8420] [--lan]

Endpoints:
  GET /              the task board
  GET /api/tasks     all tasks with project names, description and additional information,
                     and all meetings with their plan, protocol and linked task IDs
  POST /api/tasks/<id>  change status, priority, due, week or project (JSON body), via scripts/update_task.py
  POST /api/tasks/<id>/comments  add a comment ({"text": ...}), via scripts/comment_task.py
  POST /api/tasks/<id>/description  replace the description ({"text": ...}), via scripts/describe_task.py
  POST /api/tasks/<id>/links  add a link ({"url": ...}) or remove it ({"url": ..., "remove": true}), via scripts/link_task.py
  POST /api/tasks/<id>/draft  draft a message about the task with Claude ({"language": optional}); see draft.py

Binds to 127.0.0.1 only, unless --lan is given: then it listens on every network interface so other
devices on the same network (a phone, a laptop) can open it. There is no login: anyone on that network
can read and edit tasks and request message drafts, so use --lan only on a trusted network.
Data is read fresh on every request.
"""
import argparse
import json
import re
import socket
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from comment_task import add_comment  # noqa: E402
from describe_task import set_description  # noqa: E402
from link_task import change_link  # noqa: E402
from draft import DraftError, draft_message  # noqa: E402
from update_task import UpdateError, update  # noqa: E402
from validate import (CLOSED_STATUSES, MEETINGS, OPEN_STATUSES, PROFILE, PROJECTS, TASK_ID, TASKS, parse,  # noqa: E402
                      parse_list, parse_weeks)

SECTIONS = {"Description": "description", "Additional information": "additional_info", "Links": "links", "Comments": "comments",
            "Original input": "original_input"}
MEETING_SECTIONS = {"Goal": "goal", "Agenda": "agenda", "Preparation": "preparation", "Protocol": "protocol"}


def load_projects():
    projects = {}
    for path in PROJECTS.glob("*/*.md"):
        try:
            meta, _ = parse(path)
        except ValueError:
            continue
        projects[meta.get("id")] = meta
    return projects


def split_sections(body, sections=SECTIONS):
    out = {key: "" for key in sections.values()}
    for m in re.finditer(r"^## (.+?)\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S):
        key = sections.get(m.group(1).strip())
        if key:
            out[key] = m.group(2).strip()
    return out


def load_task_for_draft(task_id):
    """One task with all sections, including Original input. Used only server-side, to draft a message."""
    matches = list(TASKS.glob(f"{task_id}-*.md"))
    if len(matches) != 1:
        raise DraftError(f"Task {task_id} not found")
    meta, body = parse(matches[0])
    task = dict(meta, **split_sections(body))
    task["project_name"] = load_projects().get(meta.get("project"), {}).get("name", meta.get("project"))
    return task


def load_profile():
    try:
        return parse(PROFILE)[0]
    except (OSError, ValueError):
        return {}


def load_tasks():
    projects = load_projects()
    tasks = []
    for path in sorted(TASKS.glob("*.md")):
        try:
            meta, body = parse(path)
        except ValueError:
            continue
        task = {k: (None if v == "null" else v) for k, v in meta.items()}
        project = projects.get(task.get("project"), {})
        task["project_name"] = project.get("name", task.get("project"))
        task["is_closed"] = task.get("status") in CLOSED_STATUSES
        task["weeks"] = parse_weeks(task.get("weeks")) or []
        sections = split_sections(body)
        sections.pop("original_input")  # not shown in the app
        sections["links"] = re.findall(r"^- (\S+)\s*$", sections["links"], flags=re.M)
        task.update(sections)
        tasks.append(task)
    return tasks


def load_meetings():
    projects = load_projects()
    meetings = []
    for path in sorted(MEETINGS.glob("*.md")):
        try:
            meta, body = parse(path)
        except ValueError:
            continue
        meeting = {k: (None if v == "null" else v) for k, v in meta.items()}
        meeting["tasks"] = parse_list(meta.get("tasks"), TASK_ID) or []
        meeting["project_name"] = projects.get(meeting.get("project"), {}).get("name", meeting.get("project"))
        meeting.update(split_sections(body, MEETING_SECTIONS))  # Original input is never sent
        meetings.append(meeting)
    return meetings


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/tasks":
            payload = json.dumps({
                "tasks": load_tasks(),
                "meetings": load_meetings(),
                "statuses": {"open": sorted(OPEN_STATUSES), "closed": sorted(CLOSED_STATUSES)},
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def send_json(self, code, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        m = re.fullmatch(r"/api/tasks/(T-\d{4})(/draft|/comments|/description|/links)?", self.path)
        if not m:
            return self.send_json(404, {"error": "Not found"})
        # Only accept JSON from this page: blocks form posts from other websites.
        origin = self.headers.get("Origin")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json" or (
                origin and origin != f"http://{self.headers.get('Host')}"):
            return self.send_json(403, {"error": "Forbidden"})
        if m.group(2) == "/comments":  # POST /api/tasks/<id>/comments {"text": ...}: add a comment
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                stamp = add_comment(m.group(1), str(body.get("text") or ""))
            except (ValueError, UpdateError) as e:
                return self.send_json(400, {"error": str(e)})
            return self.send_json(200, {"added": stamp})
        if m.group(2) == "/description":  # POST /api/tasks/<id>/description {"text": ...}: replace the description
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                changed = set_description(m.group(1), str(body.get("text") or ""))
            except (ValueError, UpdateError) as e:
                return self.send_json(400, {"error": str(e)})
            return self.send_json(200, {"changed": changed})
        if m.group(2) == "/links":  # POST /api/tasks/<id>/links {"url": ..., "remove": optional}: add or remove a link
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                changed = change_link(m.group(1), str(body.get("url") or ""), bool(body.get("remove")))
            except (ValueError, UpdateError) as e:
                return self.send_json(400, {"error": str(e)})
            return self.send_json(200, {"changed": changed})
        if m.group(2):  # POST /api/tasks/<id>/draft {"language": optional}: draft a message with Claude
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                language = (body.get("language") or "").strip() or None
                result = draft_message(load_task_for_draft(m.group(1)), load_profile(), language)
            except ValueError:
                return self.send_json(400, {"error": "Bad request"})
            except DraftError as e:
                return self.send_json(502, {"error": str(e)})
            return self.send_json(200, result)
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            fields = {k: body[k] for k in ("status", "priority", "due", "week", "project") if k in body}
            fields = {k: ("null" if v is None else str(v)) for k, v in fields.items()}
            changes = update(m.group(1), **fields)
        except (ValueError, UpdateError) as e:
            return self.send_json(400, {"error": str(e)})
        self.send_json(200, {"changed": sorted(k for k in changes if k != "updated")})

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # always serve the latest page during development
        super().end_headers()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))


def lan_ip():
    """This computer's address on the local network."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 80))  # sends nothing; only picks the outgoing interface
            return s.getsockname()[0]
        except OSError:
            return "<this computer's IP>"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--lan", action="store_true", help="serve to other devices on the local network (no login)")
    args = parser.parse_args()
    server = ThreadingHTTPServer(("0.0.0.0" if args.lan else "127.0.0.1", args.port), Handler)
    print(f"Ordo Operum running at http://localhost:{args.port}", flush=True)
    if args.lan:
        print(f"On your local network: http://{lan_ip()}:{args.port}", flush=True)
        print("No login: anyone on this network can read and edit tasks.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
