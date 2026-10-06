#!/usr/bin/env python3
"""Local web app: serves the task board and a read-only JSON API over data/.

Usage:
  python3 apps/web/server.py [--port 8420]

Endpoints:
  GET /              the task board
  GET /api/tasks     all tasks with project names, description and additional information
  POST /api/tasks/<id>  change status, priority, due, week or project (JSON body), via scripts/update_task.py

Binds to 127.0.0.1 only. Data is read fresh on every request.
"""
import argparse
import json
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).resolve().parent / "static"
sys.path.insert(0, str(ROOT / "scripts"))

from update_task import UpdateError, update  # noqa: E402
from validate import CLOSED_STATUSES, OPEN_STATUSES, PROJECTS, TASKS, parse  # noqa: E402

SECTIONS = {"Description": "description", "Additional information": "additional_info", "Original input": "original_input"}


def load_projects():
    projects = {}
    for path in PROJECTS.glob("*/*.md"):
        try:
            meta, _ = parse(path)
        except ValueError:
            continue
        projects[meta.get("id")] = meta
    return projects


def split_sections(body):
    out = {key: "" for key in SECTIONS.values()}
    for m in re.finditer(r"^## (.+?)\s*\n(.*?)(?=^## |\Z)", body, flags=re.M | re.S):
        key = SECTIONS.get(m.group(1).strip())
        if key:
            out[key] = m.group(2).strip()
    return out


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
        sections = split_sections(body)
        sections.pop("original_input")  # not shown in the app
        task.update(sections)
        tasks.append(task)
    return tasks


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/api/tasks":
            payload = json.dumps({
                "tasks": load_tasks(),
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
        m = re.fullmatch(r"/api/tasks/(T-\d{4})", self.path)
        if not m:
            return self.send_json(404, {"error": "Not found"})
        # Only accept JSON from this page: blocks form posts from other websites.
        origin = self.headers.get("Origin")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json" or (
                origin and origin != f"http://{self.headers.get('Host')}"):
            return self.send_json(403, {"error": "Forbidden"})
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8420)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Ordo Operum running at http://localhost:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
