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
| `priority` | `P1`–`P5`, see below |
| `status` | See [Status](#status) |
| `due` | `YYYY-MM-DD` or `null` — the deadline |
| `week` | ISO week `YYYY-Www` (e.g. `2026-W41`, weeks start Monday) or `null` — the week the task is planned to be done. Set by `/plan`, by `/task`, by the web app, or by `/new-task` when the input says when |
| `pinned` | `true` if the user chose the week, or the task is `P1` (planning always pins P1 to the planning week). Planning never moves a pinned task except forward when its week is over. `false` otherwise |
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

## Status

| Value | Group | Meaning |
|-------|-------|---------|
| `new` | open | Captured, not started |
| `in-progress` | open | Being worked on |
| `done` | closed | Completed |
| `cancelled` | closed | Won't be done |

### Which week a task belongs to

Used by the week view and by planning agents:

1. A closed task belongs to the week of its `closed` date.
2. An open task belongs to its `week`; if that is `null`, to the week of its `due` date; if both are `null`, it is unscheduled.
3. An open task whose week is already over is carried over into the current week (and `/plan` moves it forward).

## Meetings

A meeting plan prepared by `/meeting`. File: `data/meetings/<date>-<slug>.md` (`undated-<slug>.md` when there is no date yet); `id` is the file name without `.md`.

```markdown
---
id: 2026-10-09-sales-q4-pipeline
title: Q4 pipeline review with the sales team
audience: Sales team
date: 2026-10-09
duration: 45
tier: business
project: axon-sales
status: planned
created: 2026-10-07T10:00:00+02:00
updated: 2026-10-07T10:00:00+02:00
---

## Goal

Agree on the three deals to push before year end and who owns each.

## Agenda

### 1. Pipeline status — P1 · 15 min

Where each Q4 deal stands and what blocks it.

- **Key points:** …
- **Supporting material:** …
- **Likely questions:** …
- **Outcome wanted:** …

### 2. … — P2 · 10 min

## Preparation

- Things to prepare, check or bring before the meeting. `None.` if nothing.

## Original brief

> the user's words, verbatim
```

| Field | Values |
|-------|--------|
| `title` | ≤ 80 characters |
| `audience` | Who attends, as the user describes it (e.g. `Sales team`, `Management team`) |
| `date` | `YYYY-MM-DD` or `null` |
| `duration` | Minutes, or `null` if unknown |
| `tier` | `business` or `personal` |
| `project` | ID of an existing project, or `null` if the meeting isn't tied to one |
| `status` | `planned`, `done` or `cancelled` |
| `created`, `updated` | ISO 8601 timestamps with time zone |

Agenda items are `### <n>. <title> — <priority> · <minutes> min` (minutes optional), in discussion order, with agenda priorities:

| Value | Meaning |
|-------|---------|
| `P1` | Must cover — the meeting fails without it |
| `P2` | Should cover |
| `P3` | If time allows |

The app and agents never show the Original brief; it is kept for reference only.

## Priority

| Value | Meaning |
|-------|---------|
| `P1` | 🔴 Critical — do as soon as possible, drop other work if needed |
| `P2` | High — important, do soon (days) |
| `P3` | Normal — the default (weeks) |
| `P4` | Low — can wait (months) |
| `P5` | Not important — maybe next year; fine if it never gets done |
