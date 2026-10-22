# Data Model

Shared by all agents and, in Phase 2, the apps. Enforced by `scripts/validate.py`. Change both together.

## Profile

`data/profile.md` — facts about the user that every agent uses for enrichment (nearby places, opening hours, local prices). Agents read it; only change it when the user asks.

```markdown
---
location: Omegna, Piedmont, Italy
timezone: Europe/Rome
currency: EUR
updated: 2026-10-08T17:11:56+02:00
---

## Context

- Other facts useful for enrichment.
```

| Field | Values |
|-------|--------|
| `location` | City, region, country — never a street address |
| `timezone` | IANA name, e.g. `Europe/Rome` |
| `currency` | 3-letter code prices are shown in, e.g. `EUR` |
| `updated` | ISO 8601 timestamp with time zone |

## Tiers

Fixed: `business` (work, clients, companies, products) and `personal` (home, family, health, finances, travel, learning).

## Projects

Every project belongs to one tier. Project names always come from the user; agents never invent one.

File: `data/projects/<tier>/<id>.md`, where `id` is a lowercase slug of the name (`a-z`, `0-9`, `-`), unique across both tiers.

```markdown
---
id: home
name: Home
tier: personal
status: active
created: 2026-10-05T14:00:00+02:00
---

## Description

Running the household: repairs, utilities, furniture.

## Context

- Facts agents can reuse for this project's tasks: people, links, tools, recurring details. `None yet.` until known.
```

| Field | Values |
|-------|--------|
| `id` | Must match the file name |
| `name` | Display name, as given by the user |
| `tier` | `business` or `personal`; must match the folder |
| `status` | `active` or `archived` |
| `created` | ISO 8601 timestamp with time zone |

## Tasks

Every task belongs to exactly one existing project. Every field is always present; unknown values are `null`.

File: `data/tasks/<id>-<slug>.md`, e.g. `data/tasks/T-0001-renew-car-insurance.md` (slug: lowercase, ≤ 6 words).

```markdown
---
id: T-0001
title: Renew car insurance
tier: personal
project: car
priority: P2
status: new
due: 2026-10-31
week: 2026-W43
pinned: false
weeks: [2026-W43]
repeat: null
repeat_until: null
series: null
created: 2026-10-05T14:20:00+02:00
updated: 2026-10-05T14:20:00+02:00
closed: null
source: audio
---

## Description

Renew the car insurance before it expires at the end of October. Compare at least two offers first. Done when the new policy is paid and the document is saved.

## Additional information

- Project: The car is a 2019 Skoda Octavia (from data/projects/personal/car.md).
- Research: Most insurers allow renewal up to 30 days before expiry. — [source](https://example.com), 2026-10-05

## Original input

> uh i need to renew the car insurance it ends end of october and maybe check other offers
```

| Field | Values |
|-------|--------|
| `id` | `T-NNNN`, sequential, never reused |
| `title` | ≤ 60 characters, starts with a verb |
| `tier` | Same as the project's tier |
| `project` | ID of an existing project |
| `priority` | `P1`–`P4`, see below |
| `status` | See [Status](#status) |
| `due` | `YYYY-MM-DD` or `null` — the deadline |
| `week` | ISO week `YYYY-Www` (e.g. `2026-W41`, weeks start Monday) or `null` — the week the task is planned to be done. Set by `/plan`, by `/task`, by the web app, or by `/new-task` when the input says when |
| `pinned` | `true` if the user chose the week, or the task is `P1` (planning always pins P1 to the planning week). Planning never moves a pinned task except forward when its week is over. `false` otherwise |
| `weeks` | Every week the task has been planned for, oldest first, e.g. `[2026-W40, 2026-W41]`; `[]` if never planned. Whenever `week` changes to a new value, it is appended (never removed); the last entry always equals `week`. Shows which tasks keep being carried over |
| `repeat` | `weekly` for a weekly series (see [Weekly tasks](#weekly-tasks)), otherwise `null` |
| `repeat_until` | `YYYY-MM-DD` — last day the series repeats; required when `repeat` is set (default: one year after it was created), otherwise `null` |
| `series` | For a weekly instance: the ID of its series, e.g. `T-0013`; otherwise `null` |
| `created`, `updated` | ISO 8601 timestamps with time zone; `updated` = `created` until changed |
| `closed` | ISO 8601 timestamp when the status became `done` or `cancelled`; `null` while open |
| `source` | `text` or `audio` |

Body sections, all required, in this order:

- **Description** — polished English: what to do, why, who is involved, what "done" looks like.
- **Additional information** — bullets, each starting with its kind. `None.` if empty.
  - `Project:` — from the project's Context.
  - `Place:` — where to go or whom to contact: name, address, opening hours, phone or booking link. Source link and retrieval date.
  - `Price:` — what it costs: amount in the profile currency (and the original currency if different), from where. Source link and retrieval date.
  - `Research:` — any other fact from the internet, with source link and retrieval date.
- **Original input** — the user's words, verbatim, as a quote. When a task is updated from a later input, the new fragment is appended.

## Weekly tasks

A recurring task is a **series** with a separate **instance** for every week, so each week can have its own content, status and notes.

- **Series**: a task with `repeat: weekly` and `repeat_until` (one year after creation unless the user says otherwise). It holds the general description and the default priority. It is never planned or done itself: `week: null`, `pinned: false`, `weeks: []`, `due: null`, `series: null`. It stays `new` while it repeats; it becomes `done` after `repeat_until`, or `cancelled` when the user ends it.
- **Instance**: a task with `series` set to the series' ID, `repeat: null`, `week` set to its week, `weeks: [<that week>]` and `pinned: true`. Title: the series title plus the week, e.g. `Learn Italian · Week 43`; file name `T-NNNN-<series-slug>-<year>-w<week>.md`. There is at most one instance per series and week. An instance's week never changes: it is **never carried over or moved**, because the next week has its own instance. An instance not finished in its week stays in that week as not done. Its Description starts with the series' description; the user adds that week's content to it. Original input is `> Created from weekly series T-NNNN for YYYY-Www.` plus anything the user later says about that week.
- Instances are created by `scripts/weekly.py` — one week at a time by `/plan` for the planning week, or on request for a given week (e.g. when the user adds content for a future week). Once created, an instance can be started, done, cancelled or reopened, and its priority, due date and content can change — but not its week.

## Status

| Value | Group | Meaning |
|-------|-------|---------|
| `new` | open | Captured, not started |
| `in-progress` | open | Being worked on, usually through the whole week. Planning always moves it into the planning week (pinned), so it continues week after week until it is done |
| `done` | closed | Completed |
| `cancelled` | closed | Won't be done |

### Which week a task belongs to

Used by the week view and by planning agents:

1. A closed task belongs to the week of its `closed` date.
2. An open task belongs to its `week`; if that is `null`, to the week of its `due` date; if both are `null`, it is unscheduled.
3. An open task whose week is already over is carried over into the current week (and `/plan` moves it forward) — except a weekly instance, which always stays in its own week.

## Meetings

A meeting plan, and after the meeting its protocol, made by `/ordo`. A meeting is identified by its **date** and **name** (plus **time** when two meetings with the same name fall on one day): the plan, the notes and every later input for that date and name go into the same file. Date and name are always required.

File: `data/meetings/<date>-<name-slug>.md`, e.g. `2026-10-09-sales-weekly.md`; only when another meeting with the same name is on the same day, `<date>-<HHMM>-<name-slug>.md`, e.g. `2026-10-09-1430-sales-weekly.md`. `id` is the file name without `.md`. `name-slug` is the name in lowercase with every run of other characters replaced by `-`.

```markdown
---
id: 2026-10-09-sales-weekly
name: Sales weekly
title: Q4 pipeline review with the sales team
audience: Sales team
date: 2026-10-09
time: 14:30
duration: 45
tier: business
project: axon-sales
tasks: [T-0007]
status: planned
created: 2026-10-07T10:00:00+02:00
updated: 2026-10-07T10:00:00+02:00
---

## Goal

Agree on the three deals to push before year end and who owns each.

## Agenda

### 1. Pipeline status — P1

### 2. Year-end deals and owners — P2

## Preparation

- Things to prepare, check or bring before the meeting. `None.` if nothing.

## Protocol

None yet.

## Original input

> the user's words, verbatim
```

| Field | Values |
|-------|--------|
| `name` | Short meeting name from the user, e.g. `Sales weekly`, `Management sync`. Stays the same for every meeting of a series. Never invented |
| `title` | ≤ 80 characters — this meeting's topic |
| `audience` | Who attends, as the user describes it (e.g. `Sales team`, `Management team`) |
| `date` | `YYYY-MM-DD` — required |
| `time` | Start time `HH:MM` (24-hour, profile time zone) or `null` if unknown |
| `duration` | Minutes, or `null` if unknown |
| `tier` | `business` or `personal` |
| `project` | ID of an existing project, or `null` if the meeting isn't tied to one |
| `tasks` | IDs of the tasks this meeting refers to, e.g. `[T-0002, T-0006]`; `[]` if none. Every `T-NNNN` written in Goal, Agenda, Preparation or Protocol must be listed here, and every listed task must exist. The web app shows the link on both the meeting and the task |
| `status` | `planned`, `done` or `cancelled` |
| `created`, `updated` | ISO 8601 timestamps with time zone |

Agenda items are `### <n>. <title> — <priority>`, in discussion order: just the talking point's name and priority, nothing under the heading. (`· <minutes> min` after the priority, and text under the heading, are still accepted for older meetings.) Agenda priorities:

| Value | Meaning |
|-------|---------|
| `P1` | Must cover — the meeting fails without it |
| `P2` | Should cover |
| `P3` | If time allows |

Tasks are referred to in the text as `T-NNNN title`, e.g. `T-0007 Review all Jira and Confluence licenses`.

**Protocol** is `None yet.` while the meeting is `planned`. Once it is `done`, it holds what happened, in this shape (each subsection `None.` if empty):

```markdown
## Protocol

Held 2026-10-09 · Attendees: Anna, Todd

### Decisions

- Push the three largest deals first (agenda item 1).

### Action items

- Anna — send the updated forecast — due 2026-10-12
- Me — finish T-0007 Review all Jira and Confluence licenses — due 2026-10-14

### Open points

- Pricing for the Q1 renewal is still undecided.
```

Action items for the user that became or changed tasks name the task ID. **Original input** holds the brief verbatim; the notes the protocol was written from are appended verbatim after it. The app and agents never show Original input.

## Priority

| Value | Meaning |
|-------|---------|
| `P1` | 🔴 Critical — do as soon as possible, drop other work if needed |
| `P2` | High — important, do soon (days) |
| `P3` | Normal — the default (weeks) |
| `P4` | Low — can wait (months), or someday; fine if it never gets done |
