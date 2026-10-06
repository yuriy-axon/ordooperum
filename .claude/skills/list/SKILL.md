---
name: list
description: Show the user's tasks as a table, sorted by priority. Argument open (default), closed or all. Use when the user runs /list, types just "list" (optionally followed by open, closed or all), or asks to see, show or list their tasks.
argument-hint: "[open|closed|all]"
allowed-tools: Bash(python3 scripts/list_tasks.py:*)
---

# List

1. Map the argument to a filter: `open` (default, also when empty), `closed` or `all`. Accept natural wording ("opened", "finished", "everything").
2. Run `python3 scripts/list_tasks.py <filter>`.
3. Show its output exactly as printed. Add nothing, change nothing, and don't modify any files.

Argument: $ARGUMENTS
