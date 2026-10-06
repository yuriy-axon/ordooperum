# Ordo Operum

A personal task-management system. Phase 1: AI agents (Claude Code skills) that capture, organize and act on the owner's tasks. Phase 2: web and mobile apps on the same data model. See `docs/vision.md`.

## Layout

- `.claude/skills/<agent>/SKILL.md` — one folder per agent. Agent-specific rules live only there.
- `docs/data-model.md` — the single source of truth for tasks, tiers, projects and priorities (imported below).
- `data/tasks/` — tasks, one Markdown file each.
- `data/projects/business/`, `data/projects/personal/` — projects, one Markdown file each.
- `scripts/validate.py` — checks every file in `data/` against the data model. Runs automatically after each edit (hook in `.claude/settings.json`).
- `scripts/list_tasks.py` — prints tasks as a table: `open` (default), `closed` or `all`.
- `scripts/update_task.py` — the only way to change a task's status, priority, due, week or project (used by `/task` and the web app).
- `scripts/plan.py` — weekly planning rules (used by `/plan`).
- `apps/web/` — the web app. `server.py` (Python stdlib, no dependencies) serves `static/` and a JSON API (`GET /api/tasks`, `POST /api/tasks/<id>` for edits via `scripts/update_task.py`). Run: `python3 apps/web/server.py` → http://localhost:8420. Tabs: Priority (grouped P1–P5) and Week (ISO weeks, browsable). The app shows only processed information; it never shows Original input. The front end talks to the API only, never to files, so the backend can be swapped for a hosted one later.

## Rules for every agent

- Read and write data only in `data/`, exactly in the format of `docs/data-model.md`.
- Get the next task ID from `python3 scripts/validate.py --next-id`. Never compute it by hand.
- After changing data, `python3 scripts/validate.py` must pass. Fix every error it reports.
- All stored text is in English with correct grammar. Original user input is kept verbatim.
- Never assume. Never invent facts, project names or deadlines. Whenever anything is unclear or missing, ask the user before acting.
- When a new field or value is needed (by an agent or the app), add it to `docs/data-model.md`, `scripts/validate.py` and every agent that writes tasks, all in the same change.
- Never delete tasks or projects unless the user explicitly asks.
- Timestamps come from `date -Iseconds`.

## Shortcuts

- A message that is just `list` (any case, optionally followed by `open`, `closed` or `all`) means: run the `list` skill with that argument.

## Adding an agent

1. Create `.claude/skills/<agent-name>/SKILL.md` with `name` and `description` frontmatter.
2. Put only that agent's behavior there; reference the data model instead of restating it.
3. If the agent needs new fields or values, change `docs/data-model.md` and `scripts/validate.py` together.

@docs/data-model.md
