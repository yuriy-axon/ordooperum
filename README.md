# Ordo Operum

Personal task-management system. Phase 1: AI agents in Claude Code. Phase 2: web and mobile apps.

## Agents

| Command | What it does |
|---------|--------------|
| `/new-task <text>` | Captures tasks from text or dictation, polished, de-duplicated, assigned to a project |
| `list [open\|closed\|all]` or `/list …` | Shows your tasks; open by default |
| `/task <change>` | Changes existing tasks: done, cancelled, reopened, priority, due date, week, project, text |
| `/plan` | Plans open tasks into weeks; runs automatically every Sunday for the next week |
| `/meeting <brief>` | Prepares a meeting: goal, prioritized agenda, talking points, supporting material, likely questions |

## Web app

```bash
python3 apps/web/server.py
```

Then open http://localhost:8420.

- **Priority** tab: tasks grouped P1–P5, sorted by due date in each group. Filters: open/closed/all, business/personal.
- **Week** tab (labelled with the current week number): what's planned for a week, what's done, and what's carried over from earlier weeks. Browse with ‹ › or the arrow keys.

Click a task for its details. The page reloads data when you switch back to it.

## Layout

```
CLAUDE.md                      rules every agent follows
.claude/skills/<agent>/        one folder per agent
.claude/settings.json          auto-validation hook
docs/vision.md                 what we're building
docs/data-model.md             format of tasks and projects (single source of truth)
data/profile.md                your location, time zone, currency
data/tasks/                    tasks
data/projects/business/        business projects
data/projects/personal/        personal projects
data/meetings/                 meeting plans
scripts/validate.py            checks data/ against the data model
scripts/list_tasks.py          prints tasks as a table
scripts/update_task.py         changes a task's status, priority, due, week, project
scripts/plan.py                weekly planning rules
apps/web/server.py             local web server + JSON API
apps/web/static/               the page (HTML, CSS, JS)
```
