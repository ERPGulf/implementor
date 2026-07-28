<div align="center">

# Implementor

<p><b>A project operations workspace for ERPNext implementation teams, built on the Frappe Framework.</b></p>

<p>
  <img src="https://img.shields.io/badge/frappe-v15-blue" alt="frappe version" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="license" />
  <img src="https://img.shields.io/badge/status-active-brightgreen" alt="status" />
</p>

</div>

---

## Overview

**Implementor** is a custom Frappe Desk page designed for ERPNext implementation partners and internal delivery teams.

It brings together projects, tasks, to-dos, progress tracking, delivery status, and collaboration in one workspace — replacing spreadsheets, scattered chat threads, and disconnected project boards.

The app is built around the core delivery flow:

**Projects → Tasks → To-dos**

with a live dashboard and a detail drawer for working directly inside the ERPNext ecosystem.

## Why Implementor

ERPNext implementation work is not just project management. Teams need to track:
- multi-module rollouts,
- client-specific delivery stages,
- integration work,
- training and handover,
- support after go-live,
- and accountability across project managers, consultants, and delivery leads.

Implementor is built for that reality.

## Key Features

### Delivery workspace
- Three-pane board for navigating projects, tasks, and to-dos.
- Fast filtering from project to task to to-do.
- Designed for implementation teams managing multiple client rollouts.

### Live dashboard
- Metric cards for workload and delivery visibility.
- Breakdown charts for status, urgency, stage, and division.
- Upcoming deadlines and emergency items.
- Combined view across Task and To-do records.

### Record details
- Detail drawer for Project, Task, and To-do records.
- Description, activity log, work notes, and file attachments.
- Inline context without leaving the board.

### Workflow actions
- Update status, project manager, division, and urgency directly from the board.
- Toggle to-do completion and recompute progress.
- Track reactions such as bookmark, star, love, angry, and emergency.

### Filtering and navigation
- Search by name, urgency, assignee, and completion range.
- Sort and filter by "My Work".
- One-click clear for fast reset.
- Native Frappe Quick Entry support for creating records.

### Theming and UI
- Matches Frappe and ERPNext light/dark themes.
- Scoped styling with no frontend framework dependency.
- Built for speed and low maintenance.

## Installation

```bash
bench get-app implementor <your-repo-url>
bench --site <your-site> install-app implementor
bench --site <your-site> migrate
bench build --app implementor
bench --site <your-site> clear-cache
```

Open:

```text
/app/implementor_board
```

## Configuration

Implementor extends the standard Frappe `Project`, `Task`, and `ToDo` doctypes with custom `imp_` fields.

Required fields include:
- `imp_status`
- `imp_percent`
- `imp_stage`
- `imp_division`
- `imp_division_lead`
- `imp_urgency`
- `imp_escalated`
- `imp_done`
- `imp_deadline`

Make sure these fields exist under **Setup → Customize Form** before using the app.

## API Reference

All endpoints are available under `implementor.api` and are intended to be called through `frappe.xcall`.

| Method | Description |
|---|---|
| `get_projects()` | List active projects. |
| `get_tasks(project=None)` | List tasks, optionally scoped to a project. |
| `get_todos(task=None, project=None)` | List to-dos for a task, project, or all records. |
| `set_status(doctype, name, status)` | Update the status of a Project or Task. |
| `set_project_manager(doctype, name, pm)` | Update a Project manager. |
| `set_division(doctype, name, division)` | Update a Task division. |
| `set_urgency(doctype, name, urgency)` | Update Task or To-do urgency. |
| `toggle_todo_done(todo)` | Toggle a to-do’s done state and recompute progress. |
| `assign_todo(todo, user)` | Assign a to-do to a user. |
| `toggle_reaction(doctype, name, reaction_type)` | Add or remove a reaction for the current user. |
| `add_work_note(doctype, name, text)` | Add a new note or comment. |
| `update_description(doctype, name, text)` | Update the description or notes field. |
| `add_attachment(doctype, name)` | Upload files to a record. |
| `dashboard_summary(group_by=None)` | Return dashboard metrics and breakdowns. |
| `get_users(role)` | List users for a given role. |

## Tech Notes

- Vanilla JavaScript frontend with no framework dependency.
- Single shared state object and delegated event handling.
- File upload handled with `fetch()` and `FormData`.
- Styling scoped under `.impl-board-root`.
- Built to stay close to standard Frappe conventions.

## License

MIT