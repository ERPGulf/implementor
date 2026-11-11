# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Frappe app (`pyproject.toml` targets Frappe 16 / Python 3.14; the README badge still says v15) living inside the bench at `/opt/sahana16/frappe-bench`, site `sahana16.erpgulf.com`. It has two independent surfaces sharing the same data:

1. **Desk board** for ERPGulf staff: a single Frappe Page at `/app/implementor_board` (Projects → Tasks → To-dos, dashboard, detail drawer, milestones).
2. **Client mobile app API** (`implementor/client_api.py`): REST endpoints for ERPGulf's customers (projects, milestones, AMC, servers/backups, support tickets).

There are no new core doctypes for projects/tasks: the app extends standard `Project`, `Task`, `ToDo` with custom fields (mostly `imp_*`, some `custom_*`) shipped as fixtures.

## Commands

Run from the bench root (`/opt/sahana16/frappe-bench`):

```bash
bench --site sahana16.erpgulf.com migrate            # apply doctype JSON + fixtures + patches
bench build --app implementor                        # rebuild assets after JS/CSS changes
bench --site sahana16.erpgulf.com clear-cache
bench --site sahana16.erpgulf.com export-fixtures --app implementor   # after changing custom fields/workflows/reports in Desk
bench --site sahana16.erpgulf.com run-tests --app implementor
bench --site sahana16.erpgulf.com run-tests --doctype "Support Ticket"   # single doctype test
bench --site sahana16.erpgulf.com console           # interactive frappe shell
bench --site sahana16.erpgulf.com execute implementor.client_api.check_server_status  # run a function directly
```

Lint/format is via pre-commit (ruff, ruff-format, prettier, eslint): `pre-commit run --all-files` from the app root. Ruff config is in `pyproject.toml` (line length 110). Python files mix tabs and spaces; match the surrounding file.

The only tests are the generated `test_*.py` stubs in each doctype folder; there is no meaningful test suite.

## Layout and architecture

- `implementor/hooks.py` — the wiring that matters: fixtures (Custom Field / Property Setter / Report filtered by module `Implementor`, plus the `Project Delivery Workflow` and `Task Status Workflow`), `permission_query_conditions` / `has_permission` for Task and ToDo (in `implementor/implementor/auth.py`), `doc_events` (Task/ToDo `validate` → `api.validate`; Project `before_save` → `amc.create_amc_milestone`), and cron jobs (daily/weekly task summary emails, OCI backup refresh every 10 min, server status check every 5 min). `rollup.py` and `escalation.py` hooks are **commented out**; `rollup._recompute_task_progress` is still imported and called directly from `api.toggle_todo_done` and `client_api`.
- `implementor/api.py` — backend for the desk board, called with `frappe.xcall("implementor.api.<fn>")`. Uses normal Frappe permissions.
- `implementor/milestone_apis.py` — milestone dashboard for the board.
- `implementor/amc.py` — when a Project's `imp_status` becomes `AMC`, auto-appends one `payment_milestone` row flagged `custom_is_amc`. Implementation-phase milestones vs AMC milestones are distinguished by that flag.
- `implementor/implementor/page/implementor_board/` — the whole desk UI: one large vanilla-JS file (~5.6k lines, single shared `state` object, delegated events) and CSS scoped under `.impl-board-root` with light/dark tokens. `test.css` is not loaded anywhere.
- `implementor/implementor/doctype/` — app doctypes (Support Ticket, Server, Server Activity, Payment Milestone and Project Module child tables, Training Session, Integration, Wall Post, Reaction, Implementor Settings single, etc.). `implementor/doctype/reaction` at the package root is a stray duplicate.
- `implementor/implementor/report/` — script reports; `report_pdf.py` renders any of them to PDF.
- `implementor/implementor/auth.py` — staff-vs-assignee row permissions (`is_admin`), token helpers, and the summary-email scheduler jobs.
- `implementor/patches/` + `patches.txt` — data patches (post-model-sync).

### Client API (`client_api.py`) conventions

Read the module docstring and `api-collection/collection.bru` before changing it; the mobile app depends on these contracts.

- Auth is a Frappe OAuth bearer token issued by a separate auth app (`employee_app`); this module only relies on `frappe.session.user`.
- Every endpoint starts with `_ctx(customer)`, which resolves the user's Customer via `Contact.user` + Dynamic Link, then data is read with `ignore_permissions` and scoped manually with `_check_project` / `_check_server` / `_check_ticket`. Client users have no desk permissions, so never skip this scoping.
- Errors go through `_fail(message, error_code, ExcClass)` so the response carries a top-level `error_code` (and no traceback). Use `_require(...)` for missing params (417 `missing_parameter`). Unknown project/server/to-do IDs deliberately return 403 `not_permitted` (don't reveal existence); tickets/milestones return 404 `not_found`.
- Status-like values are returned as lowercase codes via `_code()`; datetimes in services endpoints are ISO 8601 with offset via `_iso()` (ticket endpoints not yet converted).
- Roles: `Client Admin` (can sign off milestones) and `Client User`.
- Mark write endpoints `@frappe.whitelist(methods=["POST"])`.

## Rule: keep `api-collection/` in sync with the last commit

The Bruno collection in `implementor/api-collection/` is the API contract the mobile team works from, so it must always match the code. After every commit that touches an API endpoint (`client_api.py` mainly, also `api.py` / `milestone_apis.py`), and whenever asked to "update the api-collection":

1. Look at what the last commit changed: `git show HEAD --stat`, then `git show HEAD -- implementor/client_api.py` (and any other API files it touched).
2. For every whitelisted function that was added, changed or removed, update the matching `.bru` request in the right folder (`Projects/`, `Tickets/`, `Servers/`, `Home & Profile/`, `Notifications/`):
   - URL `{{baseUrl}}/api/method/implementor.client_api.<function>` and HTTP method (GET = query params, POST = form-encoded / multipart body).
   - Parameters: add new ones, remove dropped ones, keep `customer` disabled.
   - The `docs` block: response shape, field names, allowed enum values, date formats, and any new `error_code`s.
   - Add a new `.bru` file for a new endpoint, delete it for a removed one, and mark data-changing requests with ⚠️.
3. If error codes, conventions or date formats changed, also update the `docs` tables in `collection.bru`.
4. Use `{{token}}` / `{{masterToken}}` variables only. Real tokens stay in the gitignored `.env`.
5. Commit the collection update by itself, with a message that names the commit it covers.
