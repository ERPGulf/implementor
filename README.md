### Implementor

Implementor
https://erpgulf.com

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app implementor
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/implementor
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit

API Reference (implementor/api.py)

Internal reference for every whitelisted method in api.py. Keep this section updated
alongside the file — when you add/change an endpoint, update its entry here in the same commit.

Conventions used throughout


All endpoints are @frappe.whitelist() — callable via frappe.call() / frappe.xcall() from
the frontend, or /api/method/implementor.api.<name> over HTTP.
Doctype/record existence and write-permission checks are done explicitly in each mutation
(frappe.db.exists, frappe.has_permission) rather than relying solely on Frappe's default
behavior — this is deliberate, so bad calls fail with a clear message instead of a raw SQL/stack
trace.
HTML is stripped from any rich-text field (notes, description, Comment.content) before
it's returned, via the shared _strip_html() helper — API responses are always plain text.
List endpoints (get_projects, get_tasks, get_todos) return reaction_counts, wall_count,
activity, comments, attachments on every row. This is convenient but expensive at scale —
see Known limitations at the bottom before assuming this holds up with hundreds of records.


List endpoints

get_projects(filters=None)
Returns all Projects, excluding Closed by default (pass an explicit imp_status filter to
override). Each row includes: title, client, status, pm, percent, deadline,
description (from notes, HTML-stripped), remaining_days, reaction_counts, wall_count,
activity, comments, attachments.

get_tasks(project=None)
No project → every Task in the system, across all projects (each row includes project so you
can tell them apart). With project → scoped to that project only. Includes assigned_to
(parsed from Frappe's native _assign field), plus the same reaction/wall/activity/
comments/attachments set as get_projects.

get_todos(task=None, project=None)
Three modes:


No args → every Task-linked ToDo, portfolio-wide.
task= → ToDos for one specific task.
project= → every ToDo across every task belonging to that project.


task takes precedence if both are passed. Includes status (core field), priority (core
field — not currently kept in sync with anything, see Known limitations), done (custom
imp_done), urgency (custom imp_urgency).

get_tickets(filters=None)
Basic list of Support Tickets. No default filtering, no reaction/activity enrichment yet
(unlike the three above) — only built out as far as the list view.

get_integrations(project=None) / get_servers(client=None)
Basic scoped lists for the Integrations Tracker and Cloud/Server Console screens. Same
minimal shape as get_tickets — no enrichment fields yet.

get_users(role=None)


No role → every enabled User.
role="pm" → resolved via role_aliases to "Projects Manager" — confirm this mapping is
actually correct for your team, it was an assumption, not a confirmed rule.
role="<any real role name>" → users holding that role, via the Has Role child table
(not a direct filter on User, since roles aren't a plain field).


Detail endpoint

get_detail(doctype, name)
Doctype must be one of Project, Task, ToDo, Support Ticket. Returns the full document
(as_dict()) plus attachments, work_notes (core Comment), wall (custom Wall Post),
reactions, activity (last 20 Version entries). This is the single source powering the
Detail Drawer on every screen — one drawer component, four doctypes.

Mutations

FunctionWhat it doesNotesset_status(doctype, name, status)Updates imp_status (Project) or status (Task/ToDo)Goes through .save() → will enforce your Workflow transition rules, not a raw writeset_urgency(doctype, name, urgency)Updates imp_urgency on Task/ToDo onlyThrows if called on Project (no imp_urgency field there) or with a null valueset_project_manager(project, project_manager)Updates imp_project_managerValidates both project and user exist firstset_division(task, division)Updates imp_division + auto-resolves imp_division_leadLead resolution returns None if no User is flagged imp_is_division_lead=1 for that divisionassign_todo(todo, user)Updates ToDo.allocated_toDoes not touch Frappe's native _assign — see Known limitationstoggle_todo_done(todo)Flips imp_done and status (Closed/Open) togetherCascades into _recompute_task_progress → Task % → Project %toggle_reaction(doctype, name, reaction_type)Adds/removes a Reaction row for the current userReturns fresh _reaction_counts() for that recordadd_wall_post(doctype, name, text)Creates a Wall PostOpen/unmoderated — no delete endpoint yetadd_work_note(doctype, name, text)Adds a core CommentDistinct from Wall — see "Wall vs. Work Notes vs. Activity" belowadd_attachment(doctype, name)Attaches uploaded file(s) via multipart frappe.request.filesTwo versions exist — see Known limitations, pick oneupdate_description(doctype, name, description)Updates notes (Project) or description (Task/ToDo)Single entry point hides the fieldname inconsistency between doctypesconvert_ticket_to_task(ticket, project, task_type, division)Creates a Task from a Support Ticket, links both waysSets ticket status to In Progressset_ticket_status(ticket, status)Direct status writeNot permission/existence-checked yet — add guards to match the otherscreate_project(payload) / create_task(project, payload) / create_todo(task, payload)Generic create endpointsConsider whether frappe.new_doc() client-side makes these redundant for the UI's "+ New" buttons

get_task_percent(task) / get_project_percent(project)
Single-value progress lookups. Mostly redundant with what get_tasks/get_projects already
return per-row — useful only for a narrow refresh (e.g. a standalone progress-ring widget) or a
future integration that only needs the number.

Dashboard / aggregate endpoints

dashboard_summary(group_by=None)
Pulls every Task in the system (no project-open filter) and every non-Closed Project, then
computes: avg_progress, due_7d, overdue, escalated, by_status/by_urgency/by_stage/
by_division buckets, deadlines_soon, emergencies. Pass group_by="client" to also get a
per-client rollup (by_client).

Confirmed via testing: the due_7d/overdue boundary is inclusive at both 0 and 7 days —
i.e. a task due exactly today or exactly 7 days out is counted in due_7d; 8 days out is not.

notifications() / emergencies() / my_work()
Straightforward per-user or portfolio-wide feeds for the bell panel, flare panel, and a
personal "my work" view respectively.

Wall vs. Work Notes vs. Activity — don't conflate these

StreamBacked byPurposeWall (add_wall_post, get_detail().wall)Wall Post (custom doctype)Open, conversational thread — anyone can postWork Notes (add_work_note, get_detail().work_notes)core CommentMore "official" internal notesActivity (_recent_activity, get_detail().activity)core VersionAutomatic, system-generated field-change log — nobody writes to this directly

Known limitations / open items — read before extending further


priority (core ToDo field) vs. imp_urgency (custom field) — both returned by
get_todos, but only imp_urgency is actually wired to any mutation. priority will sit
stale unless you decide to keep it in sync or drop it from the response.
status (core ToDo) vs. imp_done (custom) — kept in sync by toggle_todo_done (as of
the last update), but confirm no other code path flips one without the other.
assign_todo only updates allocated_to, not Frappe's native _assign — if you want
Desk's own "Assigned To" widget/notifications to reflect ToDo reassignment, this needs
extending (see the assign_to_add/assign_to_remove alternative considered during
development).
Two versions of add_attachment exist — a multipart (frappe.request.files) version and
a base64-string-argument version. Only one should ship — pick based on expected file sizes
(multipart handles large files better; base64 is simpler to call from frappe.xcall but ~33%
larger payload and fully loaded into memory).
List endpoints are N+1 query-heavy — get_projects/get_tasks/get_todos each run 5
extra queries per row (reactions, wall count, activity, comments, attachments). Fine at
current scale (~10 records); will need batching (one query across all names at once,
grouped in Python) once real project counts climb into the hundreds.
Row-level permission scoping is not yet restrictive — every role currently sees the full
portfolio via get_projects/get_tasks regardless of assignment. Decide whether this is
acceptable for v1 (open internal visibility) or needs User Permissions / assignment-based
filtering before real client data is in the system.
dashboard_summary's task query has no project-status filter — it counts tasks belonging
to Closed projects too, unlike get_projects which excludes them by default. Confirm this
is intentional.
by_client in dashboard_summary(group_by="client") can produce a literal None dict key
for projects with no customer set — consider defaulting to "Unassigned" for consistency
with _bucket()'s "Unspecified" fallback.
Task's core status field options have reverted at least once (back to Frappe's default
Open/Working/Pending Review/... instead of Not Started/In Progress/Blocked/Done) — the
Property Setter behind this customization isn't yet in the fixtures list. Add it:


python   fixtures = [
       ...,
       {"dt": "Property Setter", "filters": [["doc_type", "=", "Task"], ["field_name", "=", "status"]]},
   ]

and re-export, so bench migrate restores it automatically if it ever resets again.
10. Assignment Rules previously failed silently with "Auto assignment failed: name 'doc' is     not defined" on every Task save — root cause was traced to empty Users tables on the rules,
not the condition syntax. Confirm this is still resolved before relying on auto-assignment
for real delivery work.
11. set_ticket_status has no existence/permission guard, unlike almost every other mutation
in this file — bring it in line with the pattern used elsewhere.

