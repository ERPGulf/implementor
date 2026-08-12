
frappe.pages['implementor_board'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'None',
		single_column: true
	});
	var assignees = [];
	var SLACK_ICON = `<svg width="16" height="16" viewBox="0 0 122.8 122.8" xmlns="http://www.w3.org/2000/svg">
  <path d="M25.8 77.6c0 7.1-5.8 12.9-12.9 12.9S0 84.7 0 77.6s5.8-12.9 12.9-12.9h12.9v12.9z" fill="#e01e5a"/>
  <path d="M32.3 77.6c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9v32.3c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9z" fill="#e01e5a"/>
  <path d="M45.2 25.8c-7.1 0-12.9-5.8-12.9-12.9S38.1 0 45.2 0s12.9 5.8 12.9 12.9v12.9z" fill="#36c5f0"/>
  <path d="M45.2 32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9H12.9C5.8 58.1 0 52.3 0 45.2s5.8-12.9 12.9-12.9z" fill="#36c5f0"/>
  <path d="M97 45.2c0-7.1 5.8-12.9 12.9-12.9s12.9 5.8 12.9 12.9-5.8 12.9-12.9 12.9H97z" fill="#2eb67d"/>
  <path d="M90.5 45.2c0 7.1-5.8 12.9-12.9 12.9s-12.9-5.8-12.9-12.9V12.9C64.7 5.8 70.5 0 77.6 0s12.9 5.8 12.9 12.9z" fill="#2eb67d"/>
  <path d="M77.6 97c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9-12.9-5.8-12.9-12.9V97z" fill="#ecb22e"/>
  <path d="M77.6 90.5c-7.1 0-12.9-5.8-12.9-12.9s5.8-12.9 12.9-12.9h32.3c7.1 0 12.9 5.8 12.9 12.9s-5.8 12.9-12.9 12.9z" fill="#ecb22e"/>
</svg>`;

	var WHATSAPP_ICON = `<svg width="16" height="16" viewBox="0 0 58 58" xmlns="http://www.w3.org/2000/svg">
  <path fill="#2CB742" d="M0,58l4.988-14.963C2.457,38.78,1,33.812,1,28.5C1,12.76,13.76,0,29.5,0S58,12.76,58,28.5
    S45.24,57,29.5,57c-4.789,0-9.299-1.187-13.26-3.273L0,58z"/>
  <path fill="#FFFFFF" d="M47.683,37.985c-1.316-2.487-6.169-5.331-6.169-5.331c-1.098-0.626-2.423-0.696-3.049,0.42
    c0,0-1.577,1.891-1.978,2.163c-1.832,1.241-3.529,1.193-5.242-0.52l-3.981-3.981l-3.981-3.981c-1.713-1.713-1.761-3.41-0.52-5.242
    c0.272-0.401,2.163-1.978,2.163-1.978c1.116-0.627,1.046-1.951,0.42-3.049c0,0-2.844-4.853-5.331-6.169
    c-1.058-0.56-2.357-0.364-3.203,0.482l-1.758,1.758c-5.577,5.577-2.831,11.873,2.746,17.45l5.097,5.097l5.097,5.097
    c5.577,5.577,11.873,8.323,17.45,2.746l1.758-1.758C48.048,40.341,48.243,39.042,47.683,37.985z"/>
</svg>`;
	var DeliverystatusOptions = [];
	var divisions = [];
	var TaskLeadOptions = [];
	var prevCol = null;
	var dashboardData = null;
	var notifications = null;
	var currentUser = frappe.session.user;
	var project_menu_actions = [
		{ act: "details", icon: "info", label: "Details & activity" },
		{ act: "gotostatus", icon: "circle-dot", label: "Change status" },
		{ act: "changepm", icon: "user-check", label: "Change project manager" },
		{ act: "gotodue", icon: "calendar-days", label: "Change Due Date" },
		{ act: "newtask", icon: "plus", label: "Add Task" },
		{ act: "copylink", icon: "copy", label: "Copy link", doc: "Project" },
		{ act: "sendslackdm", icon: "send", label: "Send to Slack direct message", doc: "Project" },
		{ act: "sendslackchannel", icon: "send", label: "Send to Slack Channel", doc: "Project" },
		{ act: "sendwhatsapp", icon: "send", label: "Send to WhatsApp", doc: "Project" }
	];

	var project_filters_fields = [{
		"field": "status", "label": "Delivery Status", "icon": "circle-dot"
	}]
	var task_filters_fields = [
		{ field: "lead", label: "Person", icon: "user" },
		{ field: "div", label: "Division", icon: "tag" }
	];
	var todosfilterfields = [
		{
			field: "status", label: "Status"
		},
		{
			field: "assignto", label: "Assign To"
		}
	]
	page.set_title('Implementor');

	var state = {
		notification_doc: "",
		notification_id: "",
		completedBy: "",
		completedOn: null,
		todoStatusFilter: "",
		todoAssignToFilter: "",
		taskLeadFilter: "",
		taskDivFilter: "",
		projectStatusFilter: "",
		colFilterField: null,
		colFilterOpen: null,
		sendPopupOpen: null,
		notifyPanelOpen: false,
		emergencyPanelOpen: false,
		view: "board",
		selectedProject: null,
		selectToDo: null,
		selectedTask: null,
		namedFilter: "",
		urgencyFilter: "",
		personFilter: "",
		minPct: 0,
		maxPct: 100,
		mineOnly: false,
		sortFilter: "",
		menu: null,
		drawer: null,
		add: false,
	}; //we use state to remember the project selected.
	function summarizeActivityEntry(entry) {
		if (!entry.data) {
			return "Created";
		}
		var parsed;
		try {
			parsed = JSON.parse(entry.data)
		}
		catch (e) {
			return "Updated"
		}
		if (parsed.changed && parsed.changed.length > 0) {
			var change = parsed.changed[0];
			return `Set ${change[0]} to ${change[2]}`;
		};
		if (parsed.added) return "Added an item";
		if (parsed.removed) return "Removed an item"
		return "Updated";
	}
	function remDays(dueDateString) {
		var today = new Date();
		today.setHours(0, 0, 0, 0);
		var due_date = new Date(dueDateString);
		due_date.setHours(0, 0, 0, 0);
		var msPerDay = 1000 * 60 * 60 * 24;
		var diff = due_date - today;
		return Math.round(diff / msPerDay);
	}
	function remDaysHours(dueDateString) {
		if (!dueDateString) {
			return { isOverdue: false, days: 0, hours: 0, totalHours: null };
		}
		var now = new Date();                     // real "right now" — not zeroed
		var due_date = new Date(dueDateString);
		var msPerHour = 1000 * 60 * 60;
		var totalHours = Math.round((due_date - now) / msPerHour);
		var isOverdue = totalHours < 0;
		var absHours = Math.abs(totalHours);
		var days = Math.floor(absHours / 24);
		var months = Math.floor(days / 30);
		var hours = absHours % 24;
		return { isOverdue: isOverdue, months: months, days: days, hours: hours, totalHours: totalHours };
	}
	function sortedBy(arr) {
		if (state.sortFilter === "name") {
			return arr.slice().sort(function (a, b) { return a.name.localeCompare(b.name); })
		}
		if (state.sortFilter === "pct") {
			return arr.slice().sort(function (a, b) { return b.percent - a.percent; })
		}
		return arr;
	}
	function isMine(value, currentUser) {
		if (!value) return false;
		var names = Array.isArray(value) ? value : String(value).split(",");
		return names.some(function (n) { return n.trim() === currentUser; });
	}

	function showFilteredProjects() {
		var filtered = testProjects.filter(function (project) {
			var mineOnly = !state.mineOnly || isMine(project.pm, currentUser)
			var match_pct = ppct(project) >= state.minPct && ppct(project) <= state.maxPct;
			// var match_single = !state.selectedProject || state.selectedProject === project.id;
			var match_name = state.namedFilter === "" || project.name.toLowerCase().includes(state.namedFilter.toLowerCase());
			var match_person_name = state.personFilter === "" || (project.pm || "").toLowerCase().includes(state.personFilter.toLowerCase());
			var match_del_status = !state.projectStatusFilter || state.projectStatusFilter == project.status
			return match_del_status && mineOnly && match_pct && match_name && match_person_name;
		}
		)
		var sorted = sortedBy(filtered);
		if (state.selectedProject) {
			var selectedIndex = sorted.findIndex(function (p) { return p.id === state.selectedProject; });
			if (selectedIndex > 0) {
				var selectedProject = sorted[selectedIndex];
				sorted.splice(selectedIndex, 1);
				sorted.unshift(selectedProject);
			}
		}
		document.getElementById("project-count").textContent = sorted.length + " projects shown";
		document.getElementById("d-projects").innerHTML = renderProjectsColumn(sorted);

	}
	function showFilteredTasks() {
		var filtered = testTasks.filter(function (task) {
			var mineOnly = !state.mineOnly || isMine(task.lead, currentUser)
			var match_project = state.selectedProject === null || task.project == state.selectedProject;
			var match_pct = pct(task) >= state.minPct && pct(task) <= state.maxPct;
			var match_name = state.selectedProject ? true : (state.namedFilter === "" || task.name.toLowerCase().includes(state.namedFilter.toLowerCase()));
			var match_urgency = state.urgencyFilter === "" || task.urgency == state.urgencyFilter;
			var match_person = state.personFilter === "" || task.lead && String(task.lead).toLowerCase().includes(state.personFilter.toLowerCase());
			var match_div = state.taskDivFilter === "" || state.taskDivFilter === (task.div || "");
			var match_lead_filter = state.taskLeadFilter === "" || state.taskLeadFilter === (task.lead || "");
			return match_lead_filter && match_div && match_pct && mineOnly && match_project && match_name && match_urgency && match_person;
		});
		var sorted = sortedBy(filtered);
		if (state.selectedTask) {
			var selectedIndex = sorted.findIndex(function (t) { return t.id === state.selectedTask; });
			if (selectedIndex > 0) {
				var selectedTask = sorted[selectedIndex];
				sorted.splice(selectedIndex, 1);
				sorted.unshift(selectedTask);
			}
		}
		var sorted = sortedBy(filtered);
		document.getElementById("task-count").textContent = sorted.length + " tasks shown";
		document.getElementById("d-tasks").innerHTML = renderTasksColumn(sorted);

	}
	function showToDosForSelectedTasks() {
		var filtered = testTodos.filter(function (todo) {
			var mineOnly = !state.mineOnly || isMine(todo.who, currentUser)
			var todo_filtered = state.selectedTask === null || todo.task == state.selectedTask;
			var match_name = state.selectedProject ? true : (state.namedFilter === "" || todo.description.toLowerCase().includes(state.namedFilter.toLowerCase()));
			var match_person = state.personFilter === "" || (todo.who || "").toLowerCase().includes(state.personFilter.toLowerCase());
			var match_urgency = state.urgencyFilter === "" || todo.urgency == state.urgencyFilter;
			var match_filter_status = state.todoStatusFilter === "" || (todo.status || "") === state.todoStatusFilter
			var match_assignee = state.todoAssignToFilter === "" || (todo.who || "") === state.todoAssignToFilter;
			// var match_single = !state.single_todo_select || todo.id === state.single_todo_select;
			return match_assignee && match_filter_status && match_name && mineOnly && todo_filtered && match_person && match_urgency;
		});
		var sorted = sortedBy(filtered);
		document.getElementById("todo-count").textContent = sorted.length + " todos shown";
		document.getElementById("d-todos").innerHTML = renderToDosColumn(sorted);
	}

	function selectProject(id) {
		state.selectedProject = id;
		state.selectedTask = null;
		state.selectToDo = null;
		loadTasks(id);
		loadTodos(undefined, id);
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();
	};
	function selectTask(id) {
		state.selectedTask = id;
		state.selectToDo = null;
		showFilteredTasks();
		loadTodos(id);
	};
	async function selectToDo(id) {
		var todo = testTodos.find(function (t) { return t.id === id; });
		todo.done = !todo.done;
		showToDosForSelectedTasks();
		try {
			var result = await frappe.xcall("implementor.api.toggle_todo_done", { todo: id });
			var task = testTasks.find(function (t) { return t.id === result.task; });
			if (task) task.percent = result.task_percent;
			var project = testProjects.find(function (p) { return p.id === result.project; });
			if (project) project.percent = result.project_percent;
		} catch (err) {
			todo.done = !todo.done;   // revert optimistic UI update
			frappe.msgprint("Could not update to-do: " + (err.message || "unknown error"));
		}
		showFilteredTasks();
		showFilteredProjects();
		showToDosForSelectedTasks();
	}
	function renderReactions(item) {
		var defs = [
			["bookmark", "🔖"],
			["star", "⭐"],
			["love", "❤"],
			["angry", "😠"],
			["emergency", "⚠"]
		];
		return defs.map(function (d) {
			var key = d[0], icon = d[1];
			var entry = (item.reactions && item.reactions[key]) || { count: 0, users: [], reacted_by_me: false };
			var count = entry.count || 0;
			var iReacted = !!entry.reacted_by_me;
			return `<button class="rbtn ${iReacted ? 'on' : ''}" data-act="react" data-id="${item.id}" data-key="${key}">${icon} ${count > 0 ? count : ""}</button>`;
		}).join("");
	}
	function metricCard(label, value, isDanger) {
		var color = isDanger && value > 0 ? "var(--text-danger)" : "var(--text-primary)";
		return `
		<div class = "d-card"
		style="padding:12px; text-align:center">
		<div class="d-meta">${label}</div>
		<div style="font-size:22px; font-weight:600; color:${color}">${value}</div>
		</div>`;
	}
	function dashList(items, isEmergency, emptyText) {
		if (!items || items.length === 0) {
			return `<div class="d-meta">${emptyText}</div>`;
		}
		return items.map(function (item) {
			return dashListRow(item, isEmergency)
		}).join("");
	}
	function dashListRow(item, isEmergency) {
		var days = remDays(item.deadline);
		var color;
		if (isEmergency) {
			color = "var(--text-danger)";
		} else if (days !== null && days < 0) {
			color = "var(--text-danger)";       // overdue - red
		} else if (days === 0) {
			color = "var(--text-warning)";       // due today - yellow
		} else {
			color = "var(--text-accent)";        // upcoming - accent
		}
		var deadlineText = isEmergency ? (item.imp_escalated ? "Escalated" : "Emergency") : dueChip(item.doctype, item.deadline);
		return `
    <div class="dash-list-row ${isEmergency ? 'is-emergency' : ''}">
      <span class="dash-name">
        ${isEmergency ? frappe.utils.icon("triangle-alert", "xs") : ""}
		<span>${item.title != null ? item.title : item.doctype == "Task" ? "No Subject" : "No Description"}</span>
        <span class="d-meta">${item.doctype}</span>
      </span>
      <span class="dash-right" style="color:${color}">${deadlineText}</span>
    </div>
  `;
	}
	function oneStatusBar(progressState, name, count, max) {
		var pct = Math.round((count / max) * 100);
		return `
		<div class="dbar-row">
		<div class="dbar-lbl">${name}</div>
		<div class="dbar-trk"><div class="dbar-fill" style="width:${pct}%"></div></div>
		<div style="width:36px; text-align:right; color:var(--text-secondary)">${!progressState ? count : count + "%"}</div>
		</div>
		`;
	}
	function statusBarSection(progressState, by_status) {
		var names = Object.keys(by_status);
		if (names.length === 0) {
			return `<div class="d-meta">No data.</div>`
		}
		var values = names.map(function (name) {
			return by_status[name]
		})
		var max = Math.max.apply(null, values);
		return names.map(function (name) {
			return oneStatusBar(progressState, name, by_status[name], max)
		}).join("")
	}
	function renderDashBoard() {
		if (!dashboardData) return;
		var d = dashboardData;
		var cardsHtml = [];
		if (!d.project_id) {
			cardsHtml.push(metricCard("Projects", d.projects));
		}
		cardsHtml.push(
			metricCard("Tasks", d.tasks),
			metricCard(d.project_id ? "Project Completed %" : "Overall Completed %", d.avg_progress + "%"),
			metricCard("Due ≤ 7 days ", d.due_7d),
			metricCard("Overdue", d.overdue, true),
			metricCard("Escalated", d.escalated, true)
		);
		cardsHtml = cardsHtml.join("");

		document.getElementById("dashboard-view").innerHTML = `
    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(140px,1fr)); gap:10px;">
    ${cardsHtml}
    </div>
    <div style="display:grid; grid-template-columns:repeat(auto-fit, minmax(280px,1fr)); gap:16px; margin-top:20px;">
        <div class="dw-sec"><div class="dw-lbl">Deadlines — soonest first</div>${dashList(d.deadlines_soon, false, "No deadlines set.")}</div>
        <div class="dw-sec"><div class="dw-lbl">Emergencies</div>${dashList(d.emergencies, true, "None right now.")}</div>
    </div>
        <div class="dw-sec"><div class="dw-lbl">TASKS BY STATUS</div>
        ${statusBarSection(false, d.by_status)}</div>
        <div class="dw-sec"><div class="dw-lbl">TASKS BY URGENCY</div>
        ${statusBarSection(false, d.by_urgency)}</div>
        <div class="dw-sec"><div class="dw-lbl">% COMPLETED BY STAGE</div>
        ${statusBarSection(true, d.stage_avg_progress)}</div>
        <div class="dw-sec"><div class="dw-lbl">OPEN TASKS BY DIVISION</div>
        ${statusBarSection(false, d.by_division)}</div>
    `;
	}
	async function loadDashboard() {
		dashboardData = await frappe.xcall("implementor.api.dashboard_summary", { project_id: state.selectedProject });
		updateEmergencyBadge(dashboardData);
		renderDashBoard();
	}
	$(page.body).html(`
		<div class="impl-board-root">
		<div style="display:flex; align-items:center; justify-content:space-between; padding:8px 10px; border-bottom:0.5px solid var(--border)">
			<div style="display:flex; align-items:center; gap:16px">
				<button id="btn-board" class="on">${frappe.utils.icon("layout-list", "xs")} Board</button>
				<button id="btn-dashboard">${frappe.utils.icon("chart-bar", "xs")} Dashboard</button>
				<div class="legend" id="project-count"></div>
				<div class="legend"><span class="dot" style="background:var(--lvl-project)"></span> Project</div>
				<div class="legend" id="task-count"></div>
				<div class="legend"><span class="dot" style="background:var(--lvl-task)"></span> Task</div>
				<div class="legend" id="todo-count"></div>
				<div class="legend"><span class="dot" style="background:var(--lvl-todo)"></span> To-do</div>
			</div>
			<div style="display:flex; align-items:center; gap:10px">
			<div style="position:relative">
			<button id="btn-notif" class="icon-btn-lg">
				${frappe.utils.icon("bell")}
				<span class="badge" id="notif-badge" style="display:none">0</span>
			</button>
			<div id="notification-panel" class="header-panel" style="display:none;"></div>
			</div>
			<div style="position:relative">
			<button id="btn-emergency" class="icon-btn-lg">
				${frappe.utils.icon("triangle-alert")}
				<span class="badge" id="emergency-badge" style="display:none">0</span>
			</button>
			<div id="emergency-panel" class="header-panel" style="display:none;"></div>
			</div>
			<div style="position:relative">
			<button id="btn-load" class="icon-btn-lg">
				${frappe.utils.icon("refresh-cw")}
				<span class="badge" style="display:none">0</span>
			</button>
			</div>
			<div style="position:relative">
				<button id="btn-add">${frappe.utils.icon("plus", "xs")} Add</button>
				<div id="add-menu" class="add-popover" style="display:none;right:0;"></div>
			</div>
			</div>
		</div>
		<div class="topbar">
		<div style="display:flex; gap:12px; padding:16px 16px 12px; flex-wrap:wrap">
		<input id="f-name" placeholder="Search project/task/to-do" />
		<select id ="f-urgency">
			<option value="">Any urgency</option>
			<option value="Emergency">Emergency</option>
			<option value="Urgent">Urgent</option>
			<option value="Normal">Normal</option>
			<option value="Low">Low</option>
		</select>
		<div id="f-person">
		</div>
		<select id ="f-sort">
			<option value="">Sort: default</option>
			<option value="pct">% complete</option>
			<option value="name">Name</option>
		</select>
		<button id="f-mine">My work</button>
		<button id="f-clear">${frappe.utils.icon("x")}  Clear</button>
		</div>
		</div>
		<div class="grid">
		<div>
			<div id="h-projects" class="d-hd">
			<div style="display:inline-flex">${frappe.utils.icon("folder", "sm")}</div>
			Projects
			<button class="d-info" data-act="colfilter" data-col="projects" style="margin-left:auto">
					${frappe.utils.icon("filter", "xs")}
			</button>
			<div id="colfilter-projects" class="filter-panel" style="display:none;"></div>
			</div>
			<div id="d-projects"></div>
			</div>
			<div>
				<div id="h-tasks" class="d-hd">
				<div style="display:inline-flex">${frappe.utils.icon("file", "sm")}</div>
				Tasks
				<button class="d-info" data-act="colfilter" data-col="tasks" style="margin-left:auto">
				${frappe.utils.icon("filter", "xs")}
				</button>
				<div id="colfilter-tasks" class="filter-panel" style="display:none;"></div>
				</div>
				<div id="d-tasks"></div>
			</div>
			<div>
				<div id="h-todos" class="d-hd">
				<div style="display:inline-flex">${frappe.utils.icon("circle-check-big", "sm")}</div>
				To-dos
				<button class="d-info" data-act="colfilter" data-col="todos" style="margin-left:auto">
					${frappe.utils.icon("filter", "xs")}
				</button>
				<div id="colfilter-todos" class="filter-panel" style="display:none;"></div>
				</div>
				<div id="d-todos"></div>
			</div>
		</div>
		<div id="drawer" style="display:none;"></div>

		<div id = "send-popup-overlay" class = "send-popup-overlay" style="display:none;">
		<div class = "send-popup">
			<div class="send-popup-header">
			<div id="send-popup-title" class="send-popup-title"> Message to Slack DM</div>
			<button data-act='cancelsend' class="d-info">${frappe.utils.icon("close", "xs")}</button>
			</div>
			<textarea id="send-popup-text" placeholder="Type your message here..."></textarea>
			<div class="send-popup-actions">
			<button class="btn btn-default btn-sm" data-act="cancelsend">Cancel</button>
			<button class="btn btn-primary btn-sm" data-act="confirmsend">Send</button>
			</div>
		</div>
		</div>

		<div id="dashboard-view" style="display:none; padding:16px;">
		</div>
		</div>
	  `);
	function scrollToSelected() {
		requestAnimationFrame(function () {
			var el = document.querySelector(".sel");
			if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
		});
	}
	function updateView() {
		document.getElementById("btn-board").classList.toggle("on", state.view === "board");
		document.getElementById("btn-dashboard").classList.toggle("on", state.view === "dashboard");
		var showBoard = state.view === "board";
		document.querySelector(".topbar").style.display = showBoard ? "block" : "none";
		document.querySelector(".grid").style.display = showBoard ? "grid" : "none";
		document.getElementById("dashboard-view").style.display = !showBoard ? "block" : "none";
		var target = showBoard ? document.querySelector(".grid") : document.getElementById("dashboard-view");
		target.style.opacity = 0;
		requestAnimationFrame(function () { target.style.opacity = 1; });
	}
	function bindColFilterHeader(headerId, col) {
		document.getElementById(headerId).addEventListener("click", function (e) {
			var colfilter = e.target.closest("[data-act='colfilter']");
			if (colfilter) {
				prevCol = state.colFilterOpen;
				state.colFilterOpen = (state.colFilterOpen === col) ? null : col;
				state.colFilterField = null;
				if (prevCol && prevCol !== col) {
					renderColFilter(prevCol);
				}
				renderColFilter(col);
				return;

			}
			var close = e.target.closest("[data-act='close']");
			if (close) {
				state.colFilterField = null;
				renderColFilter(col);
				return;
			}
			var pickField = e.target.closest("[data-act='pickfilterfield']")
			if (pickField) {
				e.stopPropagation();
				state.colFilterField = pickField.getAttribute("data-field");
				renderColFilter(col);
				return;
			}
			var setcolfilter = e.target.closest("[data-act='setcolfilter']");
			if (setcolfilter) {
				e.stopPropagation();
				var value = setcolfilter.getAttribute("data-value");
				if (col === "projects" && state.colFilterField === "status") state["projectStatusFilter"] = value;
				if (col === "tasks" && state.colFilterField === "lead") state["taskLeadFilter"] = value;
				if (col === "tasks" && state.colFilterField === "div") state["taskDivFilter"] = value;
				if (col === "todos" && state.colFilterField === "status") state["todoStatusFilter"] = value;
				if (col === "todos" && state.colFilterField === "assignto") state["todoAssignToFilter"] = value;

				state.colFilterField = null;
				state.colFilterOpen = null;
				renderColFilter(col);
				if (col === "projects") showFilteredProjects();
				if (col === "tasks") showFilteredTasks();
				if (col === "todos") showToDosForSelectedTasks();
				return;
			}

			var back = e.target.closest("[data-act='backfilterfield']");
			if (back) {
				e.stopPropagation();
				state.colFilterField = null;
				renderColFilter(col);
				return;
			}
		});
	}
	bindColFilterHeader("h-projects", "projects");
	bindColFilterHeader("h-tasks", "tasks");
	bindColFilterHeader("h-todos", "todos");
	// bindColFilterHeader("h-tasks", "tasks", "taskDivFilter");

	document.getElementById("btn-board").addEventListener("click", function (e) {
		state.view = "board";
		updateView();
	});
	document.getElementById("btn-dashboard").addEventListener("click", function (e) {
		state.view = "dashboard";
		loadDashboard().then(function () { updateView(); });
	});
	document.getElementById("btn-emergency").addEventListener("click", async function () {
		state.emergencyPanelOpen = !state.emergencyPanelOpen;
		if (state.emergencyPanelOpen && !dashboardData) {
			dashboardData = await frappe.xcall("implementor.api.dashboard_summary");
		}
		renderEmergencyPanel();
	})
	document.getElementById("btn-load").addEventListener("click", async function () {
		state.menu = null;
		state.drawer = null;
		state.namedFilter = "";
		state.personFilter = "";
		state.mineOnly = false;
		state.sortFilter = "";
		state.urgencyFilter = "";
		state.taskDivFilter = "";
		state.taskLeadFilter = "";
		state.projectStatusFilter = "";
		document.getElementById("f-name").value = "";
		document.getElementById("f-urgency").value = "";
		document.getElementById("f-person").value = "";
		// document.getElementById("f-min").value = "";
		// document.getElementById("f-max").value = "";
		document.getElementById("f-sort").value = "";
		document.getElementById("f-mine").textContent = "My work";
		state.selectedProject = null;
		state.selectedTask = null;
		state.selectToDo = null;
		loadProjects();
		loadTasks();
		loadTodos();
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();
		renderPersonFilter();

	});
	document.getElementById("btn-notif").addEventListener("click", async function () {
		state.notifyPanelOpen = !state.notifyPanelOpen;
		if (state.notifyPanelOpen) {
			notifications = await frappe.xcall("implementor.api.notifications");
		}
		renderNotifyPanel();
	})
	function renderEmergencyPanel() {
		var el = document.getElementById("emergency-panel");
		if (!state.emergencyPanelOpen) {
			el.style.display = "none";
			return;
		}
		el.style.display = "block";
		var items = (dashboardData && dashboardData.emergencies) || [];
		var rows = (!items || (items.length === 0)) ?
			`<div class="header-panel-row d-meta">No emergencies right now.</div>`
			:
			items.map(function (item) {
				var label = item.imp_escalated ? "Escalated to lead/PM" : "Flagged as emergency";
				return `
				<div class="header-panel-row" data-act="opendocurl" data-doc="${item.doctype}" data-id="${item.name}" data-eid="${item.name}" style="display:flex; gap:10px; align-items:center">
				<div style="flex:none">${frappe.utils.icon("triangle-alert", "xs")}</div>

				<div style="flex:1; min-width:0">
					<div style="display:flex; justify-content:space-between; gap:8px; font-weight:500">
					<span>${item.title || item.name}</span>
					<span class="d-meta" style="flex:none">${item.doctype}</span>
					</div>
					<div class="d-meta" style="color:var(--text-danger); margin-top:2px">${label}</div>
				</div>
				</div>
        `;
			}).join("");
		el.innerHTML = `
			<div class="header-panel-title">
			Emergencies
			<button class="d-info" data-act="close-emergency-panel">${frappe.utils.icon("close", "xs")}</button>
			</div>
			${rows}
  `;
	}
	async function loadNotifCount() {
		if (!notifications) {
			notifications = await frappe.xcall("implementor.api.notifications")
		}
		var el = document.getElementById("notif-badge")
		if (notifications && notifications.length > 0) {
			el.textContent = notifications.length;
			el.style.display = "flex"
		}
		else {
			el.style.display = "none"
		}
	}
	function updateEmergencyBadge(dashboard) {
		var el = document.getElementById("emergency-badge");
		if (dashboard && dashboard.emergencies && dashboard.emergencies.length > 0) {
			el.textContent = dashboard.emergencies.length;
			el.style.display = "flex";
		} else {
			el.style.display = "none";
		}
	}
	function notifIcon(type) {
		var icons = {
			"Mention": "at-sign",
			"Assignment": "user-plus",
			"Share": "share-2",
			"Energy Point": "star",
			"Alert": "triangle-alert",
			"Comment": "message-circle"
		};
		var name = icons[type] || "bell";
		return frappe.utils.icon(name, "xs");
	}
	function renderNotifyPanel() {
		var el = document.getElementById("notification-panel");
		if (!state.notifyPanelOpen) {
			el.style.display = "none";
			return;
		}
		el.style.display = "block";
		var items = (notifications) || [];
		var rows = (!items || (items.length === 0)) ?
			`<div class="header-panel-row d-meta">No notifications right now.</div>`
			:
			items.map(function (item) {
				return `
          <div class="header-panel-row" data-act="opendocurl" data-doc="${item.document_type}" data-id="${item.document_name}" data-notif-id="${item.name}" style="display:flex; gap:10px; align-items:flex-start">
            <div style="flex:none; padding-top:2px">${notifIcon(item.type)}</div>
            <div style="flex:1; min-width:0">
              <div style="display:flex; justify-content:space-between; gap:8px; font-weight:500">
                <span>${(item.title) || (item.subject) || item.name}</span>
                <span class="d-meta" style="flex:none">${(dueChip(item.doctype, item.deadline))}</span>
              </div>
            </div>
          </div>
        `;
			}).join("");
		el.innerHTML = `
			<div class="header-panel-title">
			Notifications
			<button class="d-info" data-act="close-notify-panel">${frappe.utils.icon("close", "xs")}</button>
			</div>
			${rows}
  `;
	}
	document.getElementById("notification-panel").addEventListener("click", async function (e) {
		if (e.target.closest("[data-act='close-notify-panel']")) {
			state.notifyPanelOpen = false;
			renderNotifyPanel();
			return;
		}
		var opendocurl = e.target.closest("[data-act='opendocurl']");
		if (!opendocurl) return;

		var doc = opendocurl.dataset.doc;
		var id = opendocurl.dataset.id;
		var notifid = opendocurl.dataset.notifId;

		if (doc === "Task") {
			var ctx = await frappe.xcall("implementor.api.resolve_task_context", { task: id });
			if (!ctx.project) return frappe.msgprint("No Project found for this Task.");
			state.selectedProject = ctx.project;
			state.selectedTask = ctx.task;
			state.selectToDo = null;
		} else {
			var ctx = await frappe.xcall("implementor.api.resolve_todo_context", { todo: id });
			if (!ctx.task || !ctx.project) return frappe.msgprint("No Task/Project found for this To-do.");
			state.selectedProject = ctx.project;
			state.selectedTask = ctx.task;
			state.selectToDo = ctx.todo;
		}
		frappe.xcall("implementor.api.read_notifications", { id: notifid }).then(function () {
			notifications = notifications.filter(function (n) {
				return n.name != notifid;
			})
			renderNotifyPanel();
			loadNotifCount();
		})
		state.view = "board";
		updateView();

		await loadTasks(state.selectedProject);
		await loadTodos(state.selectedTask, state.selectedProject);
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();
		scrollToSelected();
	});
	function acknowledgeEmergency(doctype, name, eid) {
		return frappe.xcall("implementor.api.read_emergency", { doctype: doctype, name: name }).then(function () {
			dashboardData.emergencies = dashboardData.emergencies.filter(function (item) {
				return item.name != eid;
			});
			updateEmergencyBadge(dashboardData);
			renderEmergencyPanel();
		});
	}
	document.getElementById("emergency-panel").addEventListener("click", async function (e) {
		if (e.target.closest("[data-act='close-emergency-panel']")) {
			state.emergencyPanelOpen = false;
			renderEmergencyPanel();
			return;
		}
		var opendocurl = e.target.closest("[data-act='opendocurl']");
		if (!opendocurl) return;

		var doc = opendocurl.dataset.doc;
		var id = opendocurl.dataset.id;
		var eid = opendocurl.dataset.eid;

		if (doc === "Task") {
			var ctx = await frappe.xcall("implementor.api.resolve_task_context", { task: id });
			if (!ctx.project) {
				acknowledgeEmergency(doc, id, eid)
				frappe.msgprint("No Project found for this Task.");
				return;
			}
			state.selectedProject = ctx.project;
			state.selectedTask = id;
			state.selectToDo = null;
		} else {
			var ctx = await frappe.xcall("implementor.api.resolve_todo_context", { todo: id });
			if (!ctx.task || !ctx.project) {
				acknowledgeEmergency(doc, id, eid)
				frappe.msgprint("No Task/Project found for this ToDo");
				return;
			}
			state.selectedProject = ctx.project;
			state.selectedTask = ctx.task;
			state.selectToDo = id;
		}
		acknowledgeEmergency(doc, id, eid)
		state.view = "board";
		updateView();
		await loadTasks(state.selectedProject);
		await loadTodos(state.selectedTask, state.selectedProject);
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();
		scrollToSelected();
	});
	document.getElementById("btn-add").addEventListener("click", function (e) {
		state.add = !state.add;   // simple toggle, same pattern as your menu open/close
		renderAddMenu();
	});
	function renderAddMenu() {
		var el = document.getElementById("add-menu");
		if (!state.add) {
			el.style.display = "none";
			el.innerHTML = "";
			return;
		}
		el.style.display = "block";
		el.innerHTML = `
    <div class="d-act" data-act="newproject"><div>${frappe.utils.icon("folder-plus", "sm")}</div> New project</div>
    <div class="d-act" data-act="newtask"><div>${frappe.utils.icon("file-plus", "sm")}</div> New task in project</div>
    <div class="d-act" data-act="newtodo"><div>${frappe.utils.icon("circle-check-big", "sm")}</div> New to-do in task</div>
  `;
	};
	document.getElementById("add-menu").addEventListener("click", function (e) {
		var newproject = e.target.closest("[data-act='newproject']");
		if (newproject) {
			state.add = false;
			renderAddMenu();
			frappe.new_doc(
				"Project",
				{}, // route_options
				(quick_entry) => {
					// This runs only if Quick Entry dialog is used
					if (!quick_entry || !quick_entry.dialog) {
						// Full form opened instead of Quick Entry – nothing to override
						return;
					}

					const dialog = quick_entry.dialog;

					// Override Save action
					dialog.set_primary_action(__('Save'), () => {
						const values = dialog.get_values(true); // true = validate

						frappe.call({
							method: "frappe.client.insert",
							args: {
								doc: {
									doctype: "Project",
									...values
								}
							},
							callback(r) {
								if (!r.exc) {
									frappe.msgprint(__("Project Successfully created"));
									// Optional: refresh your page data here
									// e.g. load_projects_table(page);
								}
								// Important: just hide the dialog, no redirect
								dialog.hide();
							}
						});
					});
				}
			);
			loadProjects();
			showFilteredProjects();
			return
		}
		var newtask = e.target.closest("[data-act='newtask']");
		if (newtask) {
			state.add = false;
			renderAddMenu();
			frappe.new_doc("Task", { project: state.selectedProject }, (quick_entry) => {
				if (!quick_entry || !quick_entry.dialog) {
					return
				}
				const dialog = quick_entry.dialog;
				dialog.set_primary_action(__('Save'), () => {
					const values = dialog.get_values(true); // true = validate

					frappe.call({
						method: "frappe.client.insert",
						args: {
							doc: {
								doctype: "Task",
								project: state.selectedProject,
								...values
							}
						},
						callback(r) {
							if (!r.exc) {
								frappe.msgprint(__("Task Successfully created"));
								// Optional: refresh your page data here
								// e.g. load_projects_table(page);
							}
							// Important: just hide the dialog, no redirect
							dialog.hide();
						}
					});
				});

			});
			loadTasks();
			showFilteredTasks();
			return
		};
		var newtodo = e.target.closest("[data-act='newtodo']");
		if (newtodo) {
			state.add = false;
			renderAddMenu();
			frappe.new_doc("ToDo", { reference_type: "Task", reference_name: state.selectedTask }, (quick_entry) => {
				if (!quick_entry || !quick_entry.dialog) {
					return
				}
				const dialog = quick_entry.dialog;
				dialog.set_primary_action(__('Save'), () => {
					const values = dialog.get_values(true); // true = validate

					frappe.call({
						method: "frappe.client.insert",
						args: {
							doc: {
								doctype: "ToDo",
								reference_type: "Task",
								reference_name: state.selectedTask,
								...values
							}
						},
						callback(r) {
							if (!r.exc) {
								frappe.msgprint(__("ToDo Successfully created"));
								// Optional: refresh your page data here
								// e.g. load_projects_table(page);
							}
							// Important: just hide the dialog, no redirect
							dialog.hide();
						}
					});
				});

			});
			return
		};
	});

	function renderColFilter(col) {
		var el = document.getElementById("colfilter-" + col);
		if (state.colFilterOpen !== col) {
			el.style.display = "none";
			return;
		}
		el.style.display = "block";
		if (col === "projects") {
			if (!state.colFilterField) {
				el.innerHTML = `
					<div class="filter-panel-title">Filter by</div>
					${project_filters_fields.map(function (f) {
					return `<div class="filter-panel-row" data-act="pickfilterfield" data-field="${f.field}">
					<span>${f.label}</span>
					<span class="chevron-right">${frappe.utils.icon("chevron-right", "xs")}</span>
					</div>`;
				}).join("")}
				`;
			}
			else if (state.colFilterField === "status") {
				el.innerHTML = `
	<div class="filter-panel-title">
	<span class="filter-panel-back" data-act="backfilterfield">
		<span class="back-icon">${frappe.utils.icon("chevron-left", "xs")}</span>
		<span>Delivery status</span>
	</span>
	<button class="d-info" data-act="close" style="margin-left:auto">${frappe.utils.icon("close", "xs")}</button>
	</div>
	<div class="filter-values-wrap scrollable">
		<div class="filter-opt ${state.projectStatusFilter === "" ? "on" : ""}" data-act="setcolfilter" data-value="">Any</div>
		${DeliverystatusOptions.map(function (s) {
					return `<div class="filter-opt ${state.projectStatusFilter === s ? "on" : ""}" data-act="setcolfilter" data-value="${s}">${s}</div>`;
				}).join("")}
  </div>
`;
			}

		}
		else if (col === "tasks") {
			if (!state.colFilterField) {
				el.innerHTML = `
					<div class="filter-panel-title">Filter by</div>
					${task_filters_fields.map(function (f) {
					return `<div class="filter-panel-row" data-act="pickfilterfield" data-field="${f.field}">
					<span>${f.label}</span>
					<span class="chevron-right">${frappe.utils.icon("chevron-right", "xs")}</span>
					</div>`;
				}).join("")}
				`;
			}
			else if (state.colFilterField === "lead") {
				el.innerHTML = `
    <div class="filter-panel-title">
      <span class="filter-panel-back" data-act="backfilterfield">
        <span class="back-icon">${frappe.utils.icon("chevron-left", "xs")}</span>
        <span>Person</span>
      </span>
      <button class="d-info" data-act="close" style="margin-left:auto">${frappe.utils.icon("close", "xs")}</button>
    </div>
    <div class="filter-values-wrap scrollable">
      <div class="filter-opt ${state.taskLeadFilter === "" ? "on" : ""}" data-act="setcolfilter" data-value="">Any</div>
      ${TaskLeadOptions.map(function (u) {
					return `<div class="filter-opt ${state.taskLeadFilter === u ? "on" : ""}" data-act="setcolfilter" data-value="${u}">${u}</div>`;
				}).join("")}
    </div>
  `;
			}
			else if (state.colFilterField === "div") {
				el.innerHTML = `
    <div class="filter-panel-title">
      <span class="filter-panel-back" data-act="backfilterfield">
        <span class="back-icon">${frappe.utils.icon("chevron-left", "xs")}</span>
        <span>Division</span>
      </span>
      <button class="d-info" data-act="close" style="margin-left:auto">${frappe.utils.icon("close", "xs")}</button>
    </div>
    <div class="filter-values-wrap scrollable">
      <div class="filter-opt ${state.taskDivFilter === "" ? "on" : ""}" data-act="setcolfilter" data-value="">Any</div>
      ${divisions.map(function (d) {
					var isOn = state.taskDivFilter === d;
					return `<div class="filter-opt ${isOn ? "on" : ""}" data-act="setcolfilter" data-value="${d}">${d}
				</div>
`;
				}).join("")}
    </div>
  `;
			}
		}
		else if (col === "todos") {
			if (!state.colFilterField) {
				el.innerHTML = `
				<div class="filter-panel-title" > Filter by</div>
				${todosfilterfields.map(function (f) {
					return `<div class="filter-panel-row" data-act="pickfilterfield" data-field="${f.field}">
					<span>${f.label}</span>
					<span class="chevron-right">${frappe.utils.icon("chevron-right", "xs")}</span>
					</div>`
				}).join("")
					}
				`;
			}
			else if (state.colFilterField === "status") {
				el.innerHTML = `
				<div class="filter-panel-title">
				<span class="filter-panel-back" data-act="backfilterfield">
					<span class="back-icon">${frappe.utils.icon("chevron-left", "xs")}</span>
					<span>Status</span>
				</span>
				<button class="d-info" data-act="close" style="margin-left:auto">${frappe.utils.icon("close", "xs")}</button>
				</div>
				<div class="filter-values-wrap scrollable">
				<div class="filter-opt ${state.todoStatusFilter === "" ? "on" : ""}" data-act="setcolfilter" data-value="">Any</div>
				${status_options.map(function (d) {
					var isOn = state.todoStatusFilter === d;
					return `<div class="filter-opt ${isOn ? "on" : ""}" data-act="setcolfilter" data-value="${d}">${d}
				</div>`;
				}).join("")}
				</div>
				`;
			}
			else if (state.colFilterField === "assignto") {
				el.innerHTML = `
    <div class="filter-panel-title">
      <span class="filter-panel-back" data-act="backfilterfield">
        <span class="back-icon">${frappe.utils.icon("chevron-left", "xs")}</span>
        <span>Assign To</span>
      </span>
      <button class="d-info" data-act="close" style="margin-left:auto">${frappe.utils.icon("close", "xs")}</button>
    </div>
    <div class="filter-values-wrap scrollable">
      <div class="filter-opt ${state.todoAssignToFilter === "" ? "on" : ""}" data-act="setcolfilter" data-value="">Any</div>
      ${assignees.map(function (d) {
					var isOn = state.todoAssignToFilter === d;
					return `<div class="filter-opt ${isOn ? "on" : ""}" data-act="setcolfilter" data-value="${d}">${d}
				</div>`;
				}).join("")}</div>`;

			}
		}
	}
	var status_options = [];
	async function get_todo_status_options() {
		var response = await frappe.xcall("implementor.api.get_filter_fields", {
			doctype: "ToDo",
			fieldnames: ["status"]
		});

		var field = (response || []).find(function (f) {
			return f && f.name === "status";
		});

		status_options = field && field.options ? field.options : [];
	}
	async function getCopyUrl(doc, id) {
		var url = await frappe.xcall("implementor.api.get_doc_url", { doc: doc, id: id })
		return url
	}

	function renderSendPopup() {
		var el = document.getElementById("send-popup-overlay");
		if (!state.sendPopupOpen) {
			el.style.display = "none";
			return;
		}
		el.style.display = "flex";
		var iconHtml = ""
		var titleText = ""
		if (state.sendPopupOpen.channel === "slack_dm") {
			iconHtml = SLACK_ICON;
			titleText = "Slack DM"
		}
		else if (state.sendPopupOpen.channel === "slack_channel") {
			iconHtml = SLACK_ICON;
			titleText = "Slack Channel"
		}
		else {
			iconHtml = WHATSAPP_ICON;
			titleText = "WhatsApp"
		}

		document.getElementById("send-popup-title").innerHTML = `<span class="send-popup-title-icon">${iconHtml}</span><span>Send to ${titleText}</span>`;
		document.getElementById("send-popup-text").value = "";
		setTimeout(function () {
			document.getElementById("send-popup-text").focus();
		}, 0);
		return;

	}
	document.getElementById("send-popup-overlay").addEventListener("click", function (e) {
		if (e.target === this || e.target.closest("[data-act='cancelsend']") || e.target.closest("[data-act='close']")) {
			state.sendPopupOpen = null;
			renderSendPopup();
			return;
		}

		if (e.target.closest("[data-act='confirmsend']")) {
			var text = document.getElementById("send-popup-text").value;
			if (!text || !text.trim()) {
				frappe.msgprint("Please enter a message before sending.");
				return;
			}
			var payload = state.sendPopupOpen;
			payload.message = text;
			frappe.xcall("implementor.api.send_slack_message", { mode: payload.mode, name: payload.id, doctype: payload.doc, message: payload.message }).then(function () {
				frappe.show_alert({ message: "Message sent successfully", indicator: "green" }, 3);
				state.sendPopupOpen = null;
				renderSendPopup();
				return;
			}).catch(function (err) {
				frappe.msgprint("Could not send message: " + (err.message || "unknown error"));
			})
		}
	})
	var selectedDueDate = ""
	function initDueDatePicker(doc, type) {
		if (type == "completed_on") {
			var input = document.getElementById("completed-on-input");
		}
		else {
			var input = document.getElementById("due-date-input");
		}
		if (!input) return;
		if (!window.implFlatpickr) {
			loadFlatpickr(function () {
				initDueDatePicker(doc, type)
			})
			return;
		}
		window.implFlatpickr(input, {
			inline: true,
			static: true,
			dateFormat: "Y-m-d",
			defaultDate: (type == "completed_on" ? doc.completed_on : doc.due) || null,
			appendTo: (type == "completed_on") ? document.getElementById("completed-on-calendar-container") : document.getElementById("due-date-calendar-container"),
			onChange: function (selectedDates, dateStr) {
				if (type == "completed_on") {
					state.completedOn = dateStr
				}
				else {
					selectedDueDate = dateStr
				}
			},
		})
	}
	var deadline_updated = ""
	async function saveDueDate(doc, id, dateStr) {
		deadline_updated = await frappe.xcall("implementor.api.saveDueDate", { doctype: doc, name: id, dateStr: dateStr })
		return deadline_updated;
	}
	document.getElementById("d-projects").addEventListener("click", function (e) {
		if (e.target.id === "due-date-input" || e.target.closest(".flatpickr-calendar")) {
			return;
		}
		var gotodue = e.target.closest("[data-act='gotodue']");
		if (gotodue) {
			var projectId = gotodue.getAttribute("data-id")
			var project = testProjects.find(function (p) {
				return p.id === projectId
			})
			state.menu.mode = "changedue"
			showFilteredProjects();
			requestAnimationFrame(function () {
				initDueDatePicker(project, "due-date");
			});
			return;
		}
		var setdue = e.target.closest("[data-act='savedue']");
		if (setdue) {
			var id = setdue.getAttribute("data-id")
			saveDueDate("Project", id, selectedDueDate).then(
				function (newDate) {
					var project = testProjects.find(function (p) {
						return p.id === id
					})
					if (project) project.due = newDate;
					selectedDueDate = "";
					state.menu = null;
					loadProjects();
					showFilteredProjects();

				}
			).catch(function (err) {
				frappe.msgprint("Could not update due date: " + (err.message || "unknown error"))
			})
			return;
		}
		var sendAct = e.target.closest("[data-act='sendslackdm'],[data-act='sendslackchannel'],[data-act='sendwhatsapp']");
		if (sendAct) {
			var channelMap = {
				"sendslackdm": "slack_dm",
				"sendslackchannel": "slack_channel",
				"sendwhatsapp": "whatsapp"
			}

			var act = sendAct.getAttribute("data-act");
			var doc = sendAct.getAttribute("data-doc");
			var recordId = sendAct.getAttribute("data-id");
			state.menu = null;
			showFilteredProjects();
			var modeMap = { slack_dm: "dm", slack_channel: "slack_channel", whatsapp: "whatsapp" };
			state.sendPopupOpen = { mode: modeMap[channelMap[act]], channel: channelMap[act], doc: doc, id: recordId }
			renderSendPopup();
			return;

		}
		var react = e.target.closest("[data-act='react']");
		if (react) {
			var id = react.getAttribute("data-id");
			var key = react.getAttribute("data-key");
			var doctype = "Project";
			frappe.xcall("implementor.api.toggle_reaction", { doctype: doctype, name: id, reaction_type: key })
				.then(function (reactions) {
					var item = testProjects.find(function (p) { return p.id === id; });
					item.reactions = reactions;
					showFilteredProjects();
				});
			return;
		}
		var newtask = e.target.closest("[data-act='newtask']");

		if (newtask) {
			project_id = newtask.getAttribute("data-id");
			frappe.new_doc("Task", { project: project_id }, (quick_entry) => {
				if (!quick_entry || !quick_entry.dialog) {
					return
				}
				const dialog = quick_entry.dialog;
				dialog.set_primary_action(__('Save'), () => {
					const values = dialog.get_values(true); // true = validate

					frappe.call({
						method: "frappe.client.insert",
						args: {
							doc: {
								doctype: "Task",
								project: project_id,
								...values
							}
						},
						callback(r) {
							if (!r.exc) {
								frappe.msgprint(__("Task Successfully created"));
								// Optional: refresh your page data here
								// e.g. load_projects_table(page);
							}
							// Important: just hide the dialog, no redirect
							dialog.hide();
						}
					});
				});

			});
			return
		};

		var dots = e.target.closest("[data-act='dots']")
		if (dots) {
			var id = dots.getAttribute("data-id");
			// state.selectedProject = id;
			state.menu = (state.menu && state.menu.id === id) ? null : { id: id, mode: null };
			showFilteredProjects();
			return;
		}
		var copylink = e.target.closest("[data-act='copylink']")
		if (copylink) {
			var doc = copylink.getAttribute("data-doc");
			var id = copylink.getAttribute("data-id");
			getCopyUrl(doc, id).then(function (url) {
				navigator.clipboard.writeText(url).then(function () {
					frappe.show_alert({ message: "Link copied to clipboard", indicator: "green" }, 3);
				})
			});
			return;

		}
		var info = e.target.closest("[data-act='opendrawer']");
		if (info) {
			var id = info.getAttribute("data-id");
			var type = info.getAttribute("data-type");
			state.drawer = (state.drawer && state.drawer.id === id) ? null : { id: id, type: type };
			renderDrawer();
			return;
		}
		var opt = e.target.closest("[data-act='setstatus']");
		if (opt) {
			id = opt.getAttribute("data-id");
			newstatus = opt.getAttribute("data-value");
			frappe.xcall("implementor.api.set_status", { doctype: "Project", name: id, status: newstatus }).then(
				function () {
					var project = testProjects.find(function (p) { return p.id === id; });
					project.status = newstatus;
					state.menu = null;
					showFilteredProjects();
				})
			return;
		};
		var details = e.target.closest("[data-act='details']");
		if (details) {
			id = details.getAttribute("data-id");
			state.drawer = { id: id, type: "Project" }
			state.menu = null;
			renderDrawer();
			showFilteredProjects();
			return;
		}
		var setpm = e.target.closest("[data-act='setpm']");
		if (setpm) {
			id = setpm.getAttribute("data-id");

			newpm = setpm.getAttribute("data-value");
			frappe.xcall("implementor.api.set_project_manager", { project: id, project_manager: newpm }).then(
				function () {
					var project = testProjects.find(function (p) { return p.id === id; });
					project.pm = newpm;
					state.menu = null;
					showFilteredProjects();
				})
			return;
		}
		var changepm = e.target.closest("[data-act='changepm']");
		if (changepm) {
			state.menu.mode = "changepm";
			loadOptions("pm").then(function () { showFilteredProjects(); })
			return;
		}
		var close = e.target.closest("[data-act='close']");
		if (close) {
			state.menu = null;
			showFilteredProjects();
			return;
		}
		var gotostatus = e.target.closest("[data-act='gotostatus']")
		if (gotostatus) {
			state.menu.mode = "status";
			showFilteredProjects();
			return;
		}
		var card = e.target.closest("[data-project-id]");
		if (!card) return;
		var id = card.getAttribute("data-project-id");
		selectProject(id)
	});
	async function saveCompleted(id, { completed_on, completed_by } = {}) {
		var response = await frappe.xcall("implementor.api.update_task_completion", {
			task_id: id,
			completed_on: completed_on || undefined,
			completed_by: completed_by || undefined
		})
		var out = ""
		if (completed_on) {
			out = response.completed_on
		}
		else {
			out = response.completed_by
		}
		return out
	}
	async function getProjPerc(id) {
		var response = await frappe.xcall("implementor.api.get_project_percent_by_task", {
			task_id: id,
		})
		console.log(response)
		return response.percent_complete;
	}

	document.getElementById("d-tasks").addEventListener("click", function (e) {
		var savecompletedby = e.target.closest("[data-act='savecompletedby']");
		if (savecompletedby) {
			var id = savecompletedby.getAttribute("data-id");
			var value = savecompletedby.getAttribute("data-value");
			saveCompleted(id, { "completed_by": value }).then(function (cby) {
				console.log("cby", cby)
				var task = testTasks.find(function (t) {
					return t.id === id
				})
				task.completed_by = cby;
				state.menu = null;
				showFilteredTasks();
			}).catch(function (err) {
				frappe.msgprint("Could not update completed date: " + (err.message || "unknown error"));
			})
			return;

		}
		var setcompletedby = e.target.closest("[data-act='setcompletedby'")
		if (setcompletedby) {
			var id = setcompletedby.getAttribute("data-id");
			var task = testTasks.find(function (t) {
				return t.id === id;
			})
			state.menu = { id: id, mode: "changecompletedby" };
			showFilteredTasks();
			return;

		}
		var savecompleted = e.target.closest("[data-act='savecompleted']")
		if (savecompleted) {
			var id = savecompleted.getAttribute("data-id")
			var task = testTasks.find(function (t) {
				return t.id === id
			});
			state.menu = null;
			saveCompleted(id, { "completed_on": state.completedOn }).then(function (cdate) {
				task.completed_on = cdate;
				state.menu = null;
				showFilteredTasks();
				getProjPerc(id).then(function (percent_complete) {
					var task = testTasks.find(function (t) {
						return t.id === id
					})
					var project = testProjects.find(function (pro) {
						return pro.id === task.project
					})
					project.percent_complete = percent_complete;
					state.menu = null;
					showFilteredProjects();
				})
			}).catch(function (err) {
				frappe.msgprint("Could not update completed date: " + (err.message || "unknown error"))

			})
			return;
		}
		var setcompletedon = e.target.closest("[data-act='setcompletedon']")
		if (setcompletedon) {
			console.log("clicked")
			var id = setcompletedon.getAttribute("data-id")
			var task = testTasks.find(function (t) { return t.id === id })
			state.menu = { id: id, mode: "changecompletedon" };
			showFilteredTasks();
			requestAnimationFrame(function () {
				initDueDatePicker(task, "completed_on");
			});
			return;
		}
		var savedueDate = e.target.closest("[data-act='savedue']");
		if (savedueDate) {
			var id = savedueDate.getAttribute("data-id")
			saveDueDate("Task", id, selectedDueDate).then(function (newdate) {
				var task = testTasks.find(function (t) {
					return t.id === id
				})
				if (task) task.due = newdate
				state.menu = null;
				selectedDueDate = "";
				showFilteredTasks();
			}).catch(function (err) {
				frappe.msgprint("Could not update due date: " + (err.message || "unknown error"))
			})
			return;
		}
		if (e.target.id === "due-date-input" || e.target.closest(".flatpickr-calendar")) {
			return;
		}
		var gotodue = e.target.closest("[data-act='gotodue']")
		if (gotodue) {
			var id = gotodue.getAttribute("data-id");
			var task = testTasks.find(function (t) {
				return t.id === id;
			})
			console.log(id)
			state.menu.mode = "changedue"
			showFilteredTasks();
			requestAnimationFrame(function () {
				initDueDatePicker(task, "due_date");
			});
			return;

		}

		var react = e.target.closest("[data-act='react']");
		var card = e.target.closest("[data-task-id]");
		if (!card) return;
		var id = card.getAttribute("data-task-id");
		if (react) {
			var id = react.getAttribute("data-id");
			var key = react.getAttribute("data-key");
			var doctype = "Task";
			frappe.xcall("implementor.api.toggle_reaction", { doctype: doctype, name: id, reaction_type: key })
				.then(function (reactions) {
					var item = testTasks.find(function (t) { return t.id === id; });
					item.reactions = reactions;
					showFilteredTasks();
				});
			return;
		}
		var sendAct = e.target.closest("[data-act='sendslackdm'],[data-act='sendslackchannel'],[data-act='sendwhatsapp']");
		if (sendAct) {
			var channelMap = {
				"sendslackdm": "slack_dm",
				"sendslackchannel": "slack_channel",
				"sendwhatsapp": "whatsapp"
			}

			var act = sendAct.getAttribute("data-act");
			var doc = sendAct.getAttribute("data-doc");
			state.menu = null;
			showFilteredTasks();
			var act = sendAct.getAttribute("data-act");
			var doctype = sendAct.getAttribute("data-doc");
			var recordId = sendAct.getAttribute("data-id");
			var modeMap = { slack_dm: "dm", slack_channel: "slack_channel", whatsapp: "whatsapp" };
			state.sendPopupOpen = { mode: modeMap[channelMap[act]], channel: channelMap[act], doc: doctype, id: recordId }
			renderSendPopup();
			return;

		}
		var newtodo = e.target.closest("[data-act='newtodo']");

		if (newtodo) {
			task_id = newtodo.getAttribute("data-id");
			frappe.new_doc("ToDo", { reference_type: "Task", reference_name: task_id }, (quick_entry) => {
				if (!quick_entry || !quick_entry.dialog) {
					return
				}
				const dialog = quick_entry.dialog;
				dialog.set_primary_action(__('Save'), () => {
					const values = dialog.get_values(true); // true = validate

					frappe.call({
						method: "frappe.client.insert",
						args: {
							doc: {
								doctype: "ToDo",
								reference_type: "Task",
								reference_name: task_id,
								...values
							}
						},
						callback(r) {
							if (!r.exc) {
								frappe.msgprint(__("ToDo Successfully created"));
								// Optional: refresh your page data here
								// e.g. load_projects_table(page);
							}
							// Important: just hide the dialog, no redirect
							dialog.hide();
						}
					});
				});

			});
			return
		};
		var details = e.target.closest("[data-act='details']");
		if (details) {
			id = details.getAttribute("data-id");
			state.drawer = { id: id, type: "Task" }
			state.menu = null;
			renderDrawer();
			showFilteredTasks();
			return;
		}

		var copylink = e.target.closest("[data-act='copylink']")
		if (copylink) {
			var doc = copylink.getAttribute("data-doc");
			var id = copylink.getAttribute("data-id");
			getCopyUrl(doc, id).then(function (url) {
				navigator.clipboard.writeText(url).then(function () {
					frappe.show_alert({ message: "Link copied to clipboard", indicator: "green" }, 3);
				})
			});
			return;

		}
		var dots = e.target.closest("[data-act='dots']")
		if (dots) {
			var id = dots.getAttribute("data-id");
			state.menu = (state.menu && state.menu.id === id) ? null : { id: id, mode: null };
			showFilteredTasks();
			return;
		}
		var close = e.target.closest("[data-act='close']");
		if (close) {
			state.menu = null;
			showFilteredTasks();
			return;
		}
		var gotostatus = e.target.closest("[data-act='gotostatus']")
		if (gotostatus) {
			state.menu.mode = "status";
			showFilteredTasks();
			return;
		}
		var opt = e.target.closest("[data-act='setstatus']");
		if (opt) {
			id = opt.getAttribute("data-id");
			newstatus = opt.getAttribute("data-value");
			frappe.xcall("implementor.api.set_status", { doctype: "Task", name: id, status: newstatus }).then(
				function () {
					var task = testTasks.find(function (t) { return t.id === id; });
					task.status = newstatus;
					state.menu = null;
					showFilteredTasks();
				})
			return;
		}
		var changediv = e.target.closest("[data-act='gotodivision']");
		if (changediv) {
			state.menu.mode = "changediv";
			showFilteredTasks();
			return;
		}
		var setdiv = e.target.closest("[data-act='setdiv']");
		if (setdiv) {
			id = setdiv.getAttribute("data-id");
			newdiv = setdiv.getAttribute("data-value");
			frappe.xcall("implementor.api.set_division", { task: id, division: newdiv }).then(function () {
				var task = testTasks.find(function (p) {
					return p.id === id;
				})
				task.div = newdiv;
				state.menu = null;
				showFilteredTasks();
			})
			return;
		};
		var changeurg = e.target.closest("[data-act='gotourgency']");
		if (changeurg) {
			state.menu.mode = "changeurg";
			showFilteredTasks();
			return;
		};

		var seturg = e.target.closest("[data-act='seturg']");
		if (seturg) {
			id = seturg.getAttribute("data-id");
			newurg = seturg.getAttribute("data-value");
			frappe.xcall("implementor.api.set_urgency", { doctype: "Task", name: id, urgency: newurg }).then(
				function () {
					var task = testTasks.find(function (t) { return t.id === id; });
					task.urgency = newurg;
					state.menu = null;
					showFilteredTasks();
				})
			return;
		};
		var info = e.target.closest("[data-act='opendrawer']");
		if (info) {
			var id = info.getAttribute("data-id");
			var type = info.getAttribute("data-type");
			state.drawer = (state.drawer && state.drawer.id === id) ? null : { id: id, type: type };
			renderDrawer();
			return;
		}
		selectTask(id)
	});
	document.getElementById("d-todos").addEventListener("click", function (e) {
		var savedue = e.target.closest("[data-act='savedue']")
		if (savedue) {
			var id = savedue.getAttribute("data-id");
			var todo = testTodos.find(function (f) {
				return f.id === id
			})
			saveDueDate("ToDo", id, selectedDueDate).then(function (newdate) {
				var todo = testTodos.find(function (t) {
					return t.id === id
				})
				if (todo) todo.due = newdate
				state.menu = null;
				selectedDueDate = "";
				showToDosForSelectedTasks();

			}).catch(function (err) {
				frappe.msgprint("Could not update due date: " + (err.message || "unknown error"))
			})
			return;
		}
		var gotodue = e.target.closest("[data-act='gotodue'");
		if (gotodue) {
			var id = gotodue.getAttribute("data-id");
			var todo = testTodos.find(function (f) {
				return f.id === id
			})
			state.menu = { id: id, mode: "changedue" }
			showToDosForSelectedTasks();
			requestAnimationFrame(function () {
				initDueDatePicker(todo, "due_date");
			});
			return;
		}
		var react = e.target.closest("[data-act='react']");
		var card = e.target.closest("[data-todo-id]");
		if (!card) return;
		var id = card.getAttribute("data-todo-id");
		if (react) {
			var id = react.getAttribute("data-id");
			var key = react.getAttribute("data-key");
			var doctype = "ToDo";
			frappe.xcall("implementor.api.toggle_reaction", { doctype: doctype, name: id, reaction_type: key })
				.then(function (reactions) {
					var item = testTodos.find(function (t) { return t.id === id; });
					item.reactions = reactions;
					showToDosForSelectedTasks();
				});
			return;
		}
		var dots = e.target.closest("[data-act='dots']")
		if (dots) {
			var id = dots.getAttribute("data-id");
			state.selectToDo = id
			state.menu = (state.menu && state.menu.id === id) ? null : { id: id, mode: null };
			showToDosForSelectedTasks();
			return;
		};
		var changeurg = e.target.closest("[data-act='gotourgency']");
		if (changeurg) {
			var id = changeurg.getAttribute("data-id")
			state.menu = { id: id, mode: "changeurg" }
			showToDosForSelectedTasks();
			return;
		}
		var details = e.target.closest("[data-act='details']");
		if (details) {
			id = details.getAttribute("data-id");
			state.drawer = { id: id, type: "ToDo" }
			state.menu = null;
			renderDrawer();
			showFilteredTasks();
			return;
		}
		var assignto = e.target.closest("[data-act='assignto']");
		if (assignto) {
			var id = assignto.getAttribute("data-id");
			state.menu.mode = "assignto";
			loadOptions().then(function () { showToDosForSelectedTasks(); });
			return;
		}
		var copylink = e.target.closest("[data-act='copylink']")
		if (copylink) {
			var doc = copylink.getAttribute("data-doc");
			var id = copylink.getAttribute("data-id");
			getCopyUrl(doc, id).then(function (url) {
				navigator.clipboard.writeText(url).then(function () {
					frappe.show_alert({ message: "Link copied to clipboard", indicator: "green" }, 3);
				})
			});
			return;

		}

		var setassign = e.target.closest("[data-act='assign']");
		if (setassign) {
			id = setassign.getAttribute("data-id");
			assignto_value = setassign.getAttribute("data-value");

			frappe.xcall("implementor.api.assign_todo", { todo: id, user: assignto_value }).then(function () {
				todo = testTodos.find(function (t) {
					return t.id === id;
				});
				todo.who = assignto_value;
				state.menu = null;
				showToDosForSelectedTasks();
			})
			return;

		}
		var seturg = e.target.closest("[data-act='seturg']");
		if (seturg) {
			id = seturg.getAttribute("data-id");
			neurg = seturg.getAttribute("data-value");
			frappe.xcall("implementor.api.set_urgency", { urgency: neurg, name: id, doctype: "ToDo" }).then(function () {
				var todo = testTodos.find(function (t) { return t.id === id; });
				todo.urgency = neurg;
				state.menu = null;
				showToDosForSelectedTasks();
			})
			return;
		}

		var close = e.target.closest("[data-act='close']");
		if (close) {
			state.menu = null;
			showToDosForSelectedTasks();
			return;
		}
		var gotostatus = e.target.closest("[data-act='gotostatus']")
		if (gotostatus) {
			state.menu.mode = "status";
			showToDosForSelectedTasks();
			return;
		}
		var opt = e.target.closest("[data-act='setstatus']");
		if (opt) {
			id = opt.getAttribute("data-id");
			newstatus = opt.getAttribute("data-value");
			frappe.xcall("implementor.api.set_status", { doctype: "ToDo", name: id, status: newstatus }).then(
				function () {
					var todo = testTodos.find(function (t) { return t.id === id; });
					todo.status = newstatus;
					state.menu = null;
					showToDosForSelectedTasks();
				})
			return;
		};
		var sendAct = e.target.closest("[data-act='sendslackdm'],[data-act='sendslackchannel'],[data-act='sendwhatsapp']");
		if (sendAct) {
			var channelMap = {
				"sendslackdm": "slack_dm",
				"sendslackchannel": "slack_channel",
				"sendwhatsapp": "whatsapp"
			}

			var act = sendAct.getAttribute("data-act");
			var doc = sendAct.getAttribute("data-doc");
			state.menu = null;
			showToDosForSelectedTasks();
			var act = sendAct.getAttribute("data-act");
			var doctype = sendAct.getAttribute("data-doc");
			var recordId = sendAct.getAttribute("data-id");
			var modeMap = { slack_dm: "dm", slack_channel: "slack_channel", whatsapp: "whatsapp" };
			state.sendPopupOpen = { mode: modeMap[channelMap[act]], channel: channelMap[act], doc: doctype, id: recordId }
			renderSendPopup();
			return;

		}

		var info = e.target.closest("[data-act='opendrawer']");
		if (info) {
			var id = info.getAttribute("data-id");
			var type = info.getAttribute("data-type");
			state.drawer = (state.drawer && state.drawer.id === id) ? null : { id: id, type: type };
			renderDrawer();
			return;
		}
		selectToDo(id)
	});
	document.addEventListener("click", function (e) {
		if (state.menu != null && !e.target.closest(".d-menu") && !e.target.closest("[data-act='setcompletedby']") && !e.target.closest("[data-act='setcompletedon']") && !e.target.closest("[data-act='gotodue']") && !e.target.closest("[data-act='dots']")) {
			state.menu = null;
			showFilteredProjects();
			showFilteredTasks();
			showToDosForSelectedTasks();
		};
		if (state.drawer != null && !e.target.closest("#drawer") && !e.target.closest("[data-act='closedrawer']") && !e.target.closest("[data-act='opendrawer']") && !e.target.closest("[data-act='details']")) {
			state.drawer = null;
			renderDrawer();
		}
		if (state.add != false && !e.target.closest("#btn-add") && !e.target.closest("#add-menu")) {
			state.add = false;
			renderAddMenu();
		}
		if (state.emergencyPanelOpen != false && !e.target.closest("#emergency-panel") && !e.target.closest("#btn-emergency") && !e.target.closest("#close-emergency-panel")) {
			state.emergencyPanelOpen = false;
			renderEmergencyPanel();
		}
		if (state.notifyPanelOpen != false && !e.target.closest("#notification-panel") && !e.target.closest("#btn-notif") && !e.target.closest("#close-notify-panel")) {
			state.notifyPanelOpen = false;
			renderNotifyPanel();
		}
		if (state.colFilterOpen != null && !e.target.closest("[id^='colfilter-']") && !e.target.closest("[data-act='colfilter']")) {
			var openCol = state.colFilterOpen
			state.colFilterOpen = null;
			state.colFilterField = null;
			renderColFilter(openCol);
		}
		if (!e.target.closest("[id ='f-person-trigger']")) {
			if (state.personPanelOpen) {
				state.personPanelOpen = false;
				renderPersonFilter();
			}
		}

	});
	document.getElementById("f-name").addEventListener("input", function (e) {
		state.namedFilter = e.target.value;
		showFilteredProjects()
		showFilteredTasks()
		showToDosForSelectedTasks()
	})
	document.getElementById("f-urgency").addEventListener("change", function (e) {
		state.urgencyFilter = e.target.value;
		showFilteredTasks()
		showToDosForSelectedTasks()
	});
	document.getElementById("f-person").addEventListener("click", function (e) {
		var trigger = e.target.closest("#f-person-trigger");
		if (trigger) {
			state.personPanelOpen = !state.personPanelOpen;
			document.getElementById("f-person-panel").style.display = state.personPanelOpen ? "block" : "none"
			return;
		}
		var setPersonFilter = e.target.closest("[data-act='setpersonfilter']");
		if (setPersonFilter) {
			state.personFilter = setPersonFilter.getAttribute("data-value")
			state.personPanelOpen = false;
			renderPersonFilter();
			showFilteredProjects();
			showFilteredTasks();
			showToDosForSelectedTasks();
			return;
		}
	});
	function renderPersonFilter() {
		var el = document.getElementById("f-person");
		if (!el) return;
		el.innerHTML = `
        <div id="f-person-trigger" style="height:34px; width:160px; padding:0 10px; border:0.5px solid var(--border-strong); border-radius:var(--radius); background:var(--surface-2); display:flex; align-items:center; justify-content:space-between; gap:6px; cursor:pointer; white-space:nowrap; overflow:hidden;">
            <span style="overflow:hidden; text-overflow:ellipsis;">${state.personFilter || "Any person"}</span>
            <span style="flex:none; display:inline-flex;">${frappe.utils.icon("chevron-down", "xs")}</span>
        </div>
        <div id="f-person-panel" class="filter-panel" style="display:none; top:38px; left:0;">
            <div class="filter-values-wrap scrollable">
                <div class="filter-opt ${state.personFilter === "" ? "on" : ""}" data-act="setpersonfilter" data-value="">Any</div>
                ${TaskLeadOptions.map(function (u) {
			return `<div class="filter-opt ${state.personFilter === u ? "on" : ""}" data-act="setpersonfilter" data-value="${u}">${u}</div>`;
		}).join("")}
            </div>
        </div>
    `;
	}
	// document.getElementById("f-min").addEventListener("input", function (e) {
	// 	var num = Number(e.target.value);
	// 	state.minPct = isNaN(num) ? 0 : num;
	// 	showFilteredProjects();
	// 	showFilteredTasks();
	// });
	// document.getElementById("f-max").addEventListener("input", function (e) {
	// 	var num = Number(e.target.value);
	// 	state.maxPct = isNaN(num) ? 100 : num;
	// 	showFilteredProjects();
	// 	showFilteredTasks();
	// });
	document.getElementById("f-mine").addEventListener("click", function (e) {
		state.mineOnly = !state.mineOnly;
		e.target.textContent = state.mineOnly ? "✓ My work" : "My work";
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();

	});
	document.getElementById("f-sort").addEventListener("change", function (e) {
		state.sortFilter = e.target.value;
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();

	});
	document.getElementById("f-clear").addEventListener("click", function (e) {
		state.namedFilter = "";
		state.personFilter = "";
		state.mineOnly = false;
		state.sortFilter = "";
		state.urgencyFilter = "";
		state.taskDivFilter = "";
		state.taskLeadFilter = "";
		state.projectStatusFilter = "";
		document.getElementById("f-name").value = "";
		document.getElementById("f-urgency").value = "";
		document.getElementById("f-person").value = "";
		// document.getElementById("f-min").value = "";
		// document.getElementById("f-max").value = "";
		document.getElementById("f-sort").value = "";
		document.getElementById("f-mine").textContent = "My work";
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();
		renderPersonFilter();

	});
	function renderActivityEntry(entry) {
		return `
		<div class="dw-act">
		<div class="dw-dot">•</div>
		<div>
		<div class="d-meta">${summarizeActivityEntry(entry)}</div>
		<div>
		<div class="d-meta">${entry.owner} · ${fmtDate(entry.creation)}</div>
		</div>
		</div>
		</div>
			`;
	}
	function renderActivityList(activity) {
		if (!activity || !activity.length) return "<div style='color:gray'>No activity yet.</div>"
		return activity.map(renderActivityEntry).join("")

	}
	function renderAttachments(attachments) {
		var list;
		if (!attachments || attachments.length === 0) {
			list = `<div class="d-meta">None yet.</div>`;
		} else {
			list = attachments.map(function (a) {
				return `<div class="dw-file"><div>${frappe.utils.icon("paperclip", "xs")}</div> ${a.file_name}</div>`;
			}).join("");
		}

		return `<div id="attachments-list">${list}</div>` + `
    <input type="file" id="attachment-input" multiple style="display:none" />
    <button class="d-info" data-act="addattachment" style="width:auto; padding:6px 12px; gap:6px; margin-top:8px">
      ${frappe.utils.icon("paperclip", "sm")} Add attachment
    </button>
  `;
	}
	function renderWorkNotes(notes) {
		var list = (!notes || notes.length === 0)
			? `<div class="d-meta" > No comments yet.</div> `
			: notes.map(function (n) {
				return `<div class="dw-act" ><div class="dw-dot">•</div><div><div>${n.content}</div>
				<div class="d-meta">${n.comment_email}</div></div></div> `;
			}).join("");

		return list + `
			<div style = "display:flex; gap:6px; margin-top:8px" >
      <input id="drawer-note-input" placeholder="Add a work note..." style="flex:1" />
      <button class="d-info" data-act="addnote">${frappe.utils.icon("send", "sm")}</button>
    </div>
			`;
	}

	function renderDrawer() {
		var el = document.getElementById("drawer");
		if (!state.drawer) {
			el.style.display = "none";
			return;
		}
		el.style.display = "block";
		if (state.drawer.type === "Project") {
			var project = testProjects.find(function (p) { return state.drawer.id == p.id });
			el.innerHTML = `
			<div class="dw-sec" style = "display:flex; justify-content:space-between; align-items:center" >
		<div class="dw-lbl" style="margin-bottom:0;">${frappe.utils.icon("folder")} PROJECT</div>
			<button class="d-info" data-act="closedrawer">${frappe.utils.icon("close", "sm")}</button>
		</div>
		<div class="dw-sec">
			<h3 style="margin:0 0 4px">${project.name}</h3>
			<div class="d-meta"> ${project.client} · PM: ${renderLeads(project.pm)}· ${ppct(project)}%</div>
			<div style="margin-top:8px">
			<div class="d-meta" >${frappe.utils.icon("calendar-days")} ${fmtDate(project.due)} · ${dueChip("Project", project.due)}</div></div>
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Description</div>
			<textarea id="drawer-desc"> ${project.description || ""}</textarea>
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Attachments</div>
			${renderAttachments(project.attachments)}
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Work Notes</div>
			${renderWorkNotes(project.comments)}
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Activity log</div>
			${renderActivityList(project.activity)}
		</div>
		`}
		else if (state.drawer.type === "Task") {
			var task = testTasks.find(function (t) { return state.drawer.id == t.id });
			el.innerHTML = `
			<div class="dw-sec" style = "display:flex; justify-content:space-between; align-items:center" >
			<div class="dw-lbl" style="margin-bottom:0">${frappe.utils.icon("file")} TASK</div>
			<button class="d-info" data-act="closedrawer">${frappe.utils.icon("close", "sm")}</button>
		</div>
			<div class="dw-sec">
				<h3 style="margin:0 0 4px">${task.name}</h3>
				<div class="d-meta">${task.stage} · ${task.urgency}</div>
				<div>
					<div class="d-meta" style="display:flex; flex-wrap:wrap; gap:4px; align-items:center">
						${task.div} Assigned To: ${renderLeads(task.lead)}
					</div>
				</div>
				<div style="margin-top:8px">
					<div class="d-meta">${frappe.utils.icon("calendar-days")} ${fmtDate(task.due)} · ${dueChip("Task", task.due)} · ${task.status} · ${pct(task)}%</div>
					<div style="margin-top:4px">
						<div class="d-meta" style="color:var(--text-accent)">
							${task.creation ? `<div class="d-meta" style="color:var(--text-accent)">${frappe.utils.icon("clock", "xs")} ${task.status} since ${fmtDate(task.creation)}</div>` : ""}
						</div>
					</div>
				</div>
			</div>
		</div> 
		<div class="dw-sec">
			<div class="dw-lbl">Description</div>
			<textarea id="drawer-desc">${task.description || ""}</textarea>
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Attachments</div>
			${renderAttachments(task.attachments)}
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Work Notes</div>
			${renderWorkNotes(task.comments)}
		</div>
		<div class="dw-sec">
			<div class="dw-lbl">Activity log</div>
			${renderActivityList(task.activity)}
		</div>
		`}
		else if (state.drawer.type === "ToDo") {
			var todo = testTodos.find(function (t) { return state.drawer.id == t.id });
			el.innerHTML = `
  <div class="dw-sec" style="display:flex; justify-content:space-between; align-items:center">
    <div class="dw-lbl" style="margin-bottom:0">${frappe.utils.icon("circle-check-big", "sm")} TO-DO</div>
    <button class="d-info" data-act="closedrawer">${frappe.utils.icon("close", "sm")}</button>
  </div>
  <div class="dw-sec">
    <h3 style="margin:0 0 4px">${todo.name}</h3>
    <div class="d-meta">${todo.status} · ${todo.urgency} · Assigned to: ${renderLeads(todo.who)}</div>
    <div style="margin-top:8px">
      <div class="d-meta">${frappe.utils.icon("calendar-days", "xs")} ${fmtDate(todo.due)} · ${dueChip("ToDo", todo.due)}</div>
    </div>
  </div>
  <div class="dw-sec">
    <div class="dw-lbl">Description</div>
    <textarea id="drawer-desc">${todo.description || ""}</textarea>
  </div>
  <div class="dw-sec">
    <div class="dw-lbl">Attachments</div>
    ${renderAttachments(todo.attachments)}
  </div>
  <div class="dw-sec">
    <div class="dw-lbl">Work Notes</div>
    ${renderWorkNotes(todo.comments)}
  </div>
  <div class="dw-sec">
    <div class="dw-lbl">Activity log</div>
    ${renderActivityList(todo.activity)}
  </div>
`;
		}
	};
	document.getElementById("drawer").addEventListener("keydown", function (e) {
		if (e.target.id === "drawer-note-input" && e.key === "Enter") {
			e.preventDefault();
			document.querySelector("[data-act='addnote']").click();
		}
	});
	document.getElementById("drawer").addEventListener("click", function (e) {
		var closeDrawer = e.target.closest("[data-act='closedrawer']");
		if (closeDrawer) {
			state.drawer = null;
			renderDrawer();
		};
		var addWorkNote = e.target.closest("[data-act='addnote']");
		if (addWorkNote) {
			var value = document.getElementById("drawer-note-input").value;
			if (!value.trim()) return;
			var doctype = state.drawer.type;
			var name = state.drawer.id;
			frappe.xcall("implementor.api.add_work_note",
				{
					doctype: doctype,
					name: name,
					text: value
				}).then(async function (f) {
					if (doctype === "Project") await loadProjects();
					if (doctype === "Task") await loadTasks(state.selectedProject);
					if (doctype === "ToDo") await loadTodos(state.selectedTask);
					renderDrawer();
				})
		}
		var addattachment = e.target.closest("[data-act='addattachment']")
		if (addattachment) {
			document.getElementById("attachment-input").click();
			return;
		}
	});
	async function uploadAttachment(doctype, id, files) {
		var formData = new FormData();
		formData.append("doctype", doctype);
		formData.append("name", id);
		files.forEach(function (file) {
			formData.append("files", file);
		});
		var response = await fetch('/api/method/implementor.api.add_attachment', {
			method: 'POST',
			headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
			body: formData,
		});
		if (!response.ok) {
			var friendlyMessage = "Upload failed";
			try {
				var errBody = await response.json();
				if (errBody._server_messages) {
					var messages = JSON.parse(errBody._server_messages);
					var firstMessage = JSON.parse(messages[0]);
					friendlyMessage = firstMessage.message;
				}
			} catch (e) {
				friendlyMessage = "Upload failed";
			}
			throw new Error(friendlyMessage);
		}

		var result = await response.json();
		return result.message;

	};
	document.getElementById("drawer").addEventListener("change", function (e) {
		if (e.target.id === "attachment-input" && e.target.files.length > 0) {
			var files = Array.from(e.target.files);
			var doctype = state.drawer.type;
			var id = state.drawer.id;
			var placeHolderHtml = files.map(function (f) {
				return `<div class="uploading-row">${frappe.utils.icon("upload", "xs")} Uploading ${f.name}...</div>`;
			}).join("");
			var listEl = document.getElementById("attachments-list");
			listEl.insertAdjacentHTML("beforeend", placeHolderHtml);
			uploadAttachment(doctype, id, files).then(async function (f) {
				if (doctype === "Project") await loadProjects();
				if (doctype === "Task") await loadTasks(state.selectedProject);
				if (doctype === "ToDo") await loadTodos(state.selectedTask);
				renderDrawer();
			}).catch(function (error) { frappe.msgprint("could not upload Attachment" + error) });
		};
	});
	document.getElementById("drawer").addEventListener("blur", function (e) {
		if (e.target.id === "drawer-desc") {
			var newDesc = e.target.value;
			var doctype = state.drawer.type;
			var id = state.drawer.id;
			frappe.xcall("implementor.api.update_description",
				{ doctype: doctype, name: id, description: newDesc }
			).catch(function (err) {
				frappe.msgprint("Could not save description: " + err.message || "unknown error")
			});
		}
	}, true);


	function fmtDate(dueDateSting) {
		if (!dueDateSting) return "null";
		var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
		var d = new Date(dueDateSting);
		return d.getDate() + " " + months[d.getMonth()];
	}
	function renderLeads(lead) {
		var names = Array.isArray(lead) ? lead : (lead ? String(lead).split(",") : []);
		names = names.map(function (n) { return n.trim(); });
		names = names.filter(function (name, i) { return names.indexOf(name) === i; });

		if (names.length === 0) {
			return `<span style = "color:var(--text-muted); font-size:11px" > Unassigned</span>`;
		}

		return names.map(function (name) {
			return `<span class="d-chip" style = "background:var(--surface-1); color:var(--text-secondary)" > ${frappe.utils.icon("user", "xs")} ${name}</span>`;
		}).join(" ");
	}
	function dueChip(doc, dueDateString) {
		var r = remDaysHours(dueDateString);
		if (r.totalHours === 0) {
			return `<span style="color:orange">Due now</span>`;
		}
		if (!r.isOverdue) {
			if (r.totalHours === null) {
				return `<span>Deadline not set</span>`;
			}
			else {
				var label = r.days > 0 ? (r.days + "d " + r.hours + "h left") : (r.hours + "h left");
				return `<span>${label}</span>`;
			}
		}
		// if (doc === "Project") {
		// 	var overdueLabel = r.months > 0 ? (r.months + "mo " + r.hours + "h overdue") : (r.hours + "h overdue");
		// 	return `<span style="color:var(--text-danger)">${overdueLabel}</span>`;
		// }
		var overdueLabel = r.months > 0 ? (r.months + "mo " + r.hours + "h overdue") : r.days > 0 ? (r.days + "d " + r.hours + "h overdue") : (r.hours + "h overdue");
		return `<span style="color:var(--text-danger)">${overdueLabel}</span>`;
	}
	// indicator to mark urgency
	function urg(urgency) {
		var colors = {
			"Emergency": ["var(--text-danger)", "var(--bg-danger)"],
			"Urgent": ["var(--text-warning)", "var(--bg-warning)"],
			"Normal": ["var(--text-secondary)", "var(--surface-1)"],
			"Low": ["var(--text-muted)", "var(--surface-1)"]
		};
		var pair = colors[urgency] || colors["Normal"];
		return `<span class="d-chip" style = "color:${pair[0]}; background:${pair[1]}; border:0.5px solid ${pair[0]}" > ${urgency}</span>`;
	}
	// indicator to mark status colour
	function chip(status) {
		var colors = {
			"Discovery": ["var(--text-info)", "var(--bg-info)"],
			"AMC": ["var(--text-success)", "var(--bg-success)"],
			"Active": ["var(--text-accent)", "var(--bg-accent)"],
			"Config": ["var(--text-accent)", "var(--bg-accent)"],
			"Data Migration": ["var(--text-accent)", "var(--bg-accent)"],
			"Integration": ["var(--text-warning)", "var(--bg-warning)"],
			"UAT": ["var(--text-warning)", "var(--bg-warning)"],
			"Training": ["var(--text-success)", "var(--bg-success)"],
			"Go-Live": ["var(--text-danger)", "var(--bg-danger)"],
			"Hypercare": ["var(--text-warning)", "var(--bg-warning)"],
			"Closed": ["var(--text-muted)", "var(--surface-1)"],
			"Done": ["var(--text-success)", "var(--bg-success)"],
			"Low": ["var(--text-muted)", "var(--surface-1)"],
			"Medium": ["var(--text-warning)", "var(--bg-warning)"],
			"High": ["var(--text-danger)", "var(--bg-danger)"],
			"Open": ["var(--text-info)", "var(--bg-info)"],
			"Working": ["var(--text-accent)", "var(--bg-accent)"],
			"Pending Review": ["var(--text-warning)", "var(--bg-warning)"],
			"Overdue": ["var(--text-danger)", "var(--bg-danger)"],
			"Template": ["var(--text-muted)", "var(--surface-1)"],
			"Completed": ["var(--text-success)", "var(--bg-success)"],
			"Cancelled": ["var(--text-muted)", "var(--surface-1)"]
		};

		var pair = colors[status] || ["var(--text-muted)", "var(--surface-1)"];
		return `<span class="d-chip" style = "color:${pair[0]}; background:${pair[1]}; border:0.5px solid ${pair[0]}" > ${status}</span>`;
	}
	function renderProjectMenuCards(project) {
		return project_menu_actions.map(function (p) {
			var docAttr = p.doc ? ` data-doc="${p.doc}"` : "";
			return `
			<div class="d-act" data-act="${p.act}" data-id="${project.id}"${docAttr}>
			<div>
			${frappe.utils.icon(p.icon, "sm")}
			</div>
			${p.label}
			</div>
			`
		}).join("");
	}
	var task_menu_actions = [
		{ act: "details", icon: "info", label: "Details & activity" },
		{ act: "gotostatus", icon: "circle-dot", label: "Change status" },
		{ act: "gotodivision", icon: "tag", label: "Change Division" },
		{ act: "gotourgency", icon: "flame", label: "Set Urgency" },
		{ act: "gotodue", icon: "calendar-days", label: "Change Due date" },
		{ act: "newtodo", icon: "plus", label: "Add ToDo" },
		{ act: "copylink", icon: "copy", label: "Copy link", doc: "Task" },
		{ act: "sendslackdm", icon: "send", label: "Send to Slack direct message", doc: "Task" },
		{ act: "sendslackchannel", icon: "send", label: "Send to Slack Channel", doc: "Task" },
		{ act: "sendwhatsapp", icon: "send", label: "Send to WhatsApp", doc: "Task" }
	];
	function renderTaskMenuCards(task) {
		return task_menu_actions.map(function (p) {
			var docAttr = p.doc ? ` data-doc="${p.doc}"` : "";
			return `
			<div class="d-act" data-act="${p.act}" data-id="${task.id}"${docAttr}>
			<div>
			${frappe.utils.icon(p.icon, "sm")}
			</div>
			${p.label}
			</div>
			`
		}).join("");
	}
	function prog(percent) {
		return `
			<div style = "display:flex; align-items:center; gap:6px; margin-top:4px" >
      <div class="d-bar">
        <div class="d-fill" style="width:${percent}%"></div>
      </div>
      <span class="d-meta">${percent}%</span>
    </div>
			`;
	}
	function renderProjectCard(project) {
		var menuHtml = "";
		if (state.menu && state.menu.id === project.id) {
			if (state.menu.mode === "status") {
				get_deliv_options();
				menuHtml = `
			<div class = "d-menu" >
				<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Status</div>
				<div style="display:flex; flex-wrap:wrap; gap:6px">
                ${DeliverystatusOptions.map(status => `
                    <div class="d-opt" data-act="setstatus" data-id="${project.id}" data-value="${status}">${status}</div>
                `).join("")}
				</div>
				</div>
			`;
			}
			else if (state.menu.mode === "changepm") {
				menuHtml = `
			<div class="d-menu" >
			<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Project manager</div>
			<div style="display:flex; flex-wrap:wrap; gap:6px">
			${OptionalHtml}
			</div>
			</div>
			`;
			}
			else if (state.menu.mode === "changedue") {
				menuHtml = `
				<div class="d-menu">
					<div class="due-date-picker-wrapper">
						<div class="due-date-label">Due date</div>
						<div class="due-date-input-row">
							<input type="text" data-act="changeduedate" id="due-date-input" data-id="${project.id}"
								value="${frappe.datetime.str_to_user(project.due)}"
								placeholder="Select Date"
								style="width:auto; max-width:180px; padding:6px 10px" autocomplete="off" readonly/>
						</div>
						<div id="due-date-calendar-container"></div>
						<div class="due-date-footer">
							<button class="btn btn-default btn-sm" data-doc="projects" data-act="close">Cancel</button>
							<button class="btn btn-primary btn-sm" data-act="savedue" data-id="${project.id}">Save</button>
						</div>
					</div>
				</div>
				`;
			}

			else {
				menuHtml = `
			<div class="d-menu" >
			${renderProjectMenuCards(project)}
    <div class="d-act" data-act="close"><div>${frappe.utils.icon("close", "sm")}</div> Close</div>
  </div>
			`;
			}
		}
		return `
			<div class="d-row lvl-project ${project.id === state.selectedProject ? 'sel' : ''}" data-project-id=${project.id}>
		<div style="display:flex; flex-direction:column; gap:6px; flex:1">
			<div style="font-weight:500">${project.name}</div>
			<div class="d-meta">${project.client}</div>
			<div>${chip(project.status)}</div>
			<div class="d-own">PM · ${renderLeads(project.pm)}</div>
			<div class="d-meta">${fmtDate(project.due)} · ${dueChip("Project", project.due)}</div>
			${prog(project.percent_complete)}
			<div style="display:flex; gap:6px">${renderReactions(project)}</div>
		</div>
		<button class="d-dots" data-act="dots" data-id="${project.id}">${frappe.utils.icon("dot-vertical", "sm")}</button>
		<button class="d-info" data-act="opendrawer" data-type="Project" data-id="${project.id}">${frappe.utils.icon("info", "sm")}</button>
		${menuHtml}
		</div>
			`;
	}
	var OptionalHtml = "";
	async function loadOptions(role) {
		OptionalHtml = await list_users(role);
	}
	async function list_users(role) {
		var users = await frappe.xcall("implementor.api.get_users", { role: role });
		var id = ""
		if (role === "pm") {
			var id = state.selectedProject;
			return users.map(function (user) {
				return `<div class="d-opt" data-act="setpm" data-id="${id}" data-value="${user.name}">${user.name}</div>`
			}).join("");
		}
		else {
			var id = state.selectToDo;
			return users.map(function (user) {
				return `<div class="d-opt" data-act="assign" data-id="${id}" data-value="${user.name}">${user.name}</div>`
			}).join("");
		}
	}
	function renderTaskCard(task) {
		var menuHtml = "";
		if (state.menu && state.menu.id === task.id) {
			if (state.menu.mode === "status") {
				menuHtml = `
			<div class = "d-menu" >
				<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Status</div>
				<div style="display:flex; flex-wrap:wrap; gap:6px">
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Open">Open</div>
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Working">Working</div>
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Pending Review">Pending Review</div>
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Overdue">Overdue</div>
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Template">Template</div>
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Completed">Completed</div>
				<div class="d-opt" data-act="setstatus" data-id="${task.id}" data-value="Cancelled">Cancelled</div>
				</div>
				</div>
			`;
			}
			else if (state.menu.mode === "changediv") {
				menuHtml = `
			<div class="d-menu" >
					<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Division (sets lead)</div>
					<div style="display:flex; flex-wrap:wrap; gap:6px">
					<div class = "d-opt"  data-act="setdiv" data-id="${task.id}" data-value="Functional">Functional</div>
					<div class = "d-opt" data-act="setdiv" data-id="${task.id}" data-value="Technical">Technical</div>
					<div class = "d-opt" data-act="setdiv" data-id="${task.id}" data-value="Infra-Cloud">Infra-Cloud</div>
					</div>
					</div>
			`;
			}
			else if (state.menu.mode === "changeurg") {
				menuHtml = `
			<div class="d-menu" >
					<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Division (sets lead)</div>
					<div style="display:flex; flex-wrap:wrap; gap:6px">
					<div class = "d-opt"  data-act="seturg" data-id="${task.id}" data-value="Emergency">Emergency</div>
					<div class = "d-opt" data-act="seturg" data-id="${task.id}" data-value="Urgent">Urgent</div>
					<div class = "d-opt" data-act="seturg" data-id="${task.id}" data-value="Normal">Normal</div>
					<div class = "d-opt" data-act="seturg" data-id="${task.id}" data-value="Low">Low</div>
					</div>
					</div>
			`;
			}
			else if (state.menu.mode === "changedue") {
				menuHtml = `
<div class="d-menu">
	<div class="due-date-picker-wrapper">
		<div class="due-date-label">Due date</div>
		<div class="due-date-input-row">
			<input type="text" data-act="changeduedate" id="due-date-input" data-id="${task.id}"
				value="${frappe.datetime.str_to_user(task.due)}"
				placeholder="Select Date"
				style="width:auto; max-width:180px; padding:6px 10px" autocomplete="off" readonly/>
		</div>
		<div id="due-date-calendar-container"></div>
		<div class="due-date-footer">
			<button class="btn btn-default btn-sm" data-doc="projects" data-act="close">Cancel</button>
			<button class="btn btn-primary btn-sm" data-act="savedue" data-id="${task.id}">Save</button>
		</div>
	</div>
</div>
`;
			}
			else if (state.menu.mode === "changecompletedon") {
				menuHtml = `
				<div class="d-menu">
					<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Due date</div>
					<div style="display:flex; flex-direction:column; gap:8px">
						<input type="hidden" id="completed-on-input" data-id="${task.id}" value="${task.completed_on || ''}" />

						<div id="completed-on-calendar-container" data-id="${task.id}"></div>
						<div style="display:flex; gap:6px; justify-content:flex-end">
							<button class="btn btn-default btn-sm" data-doc="tasks" data-act="close">Cancel</button>
							<button class="btn btn-primary btn-sm" data-act="savecompleted" data-id="${task.id}">Save</button>
						</div>
					</div>
				</div>
				`;
			}
			else if (state.menu.mode === "changecompletedby") {
				menuHtml = `
	<div class="d-menu">
		<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Completed by</div>
		<div class="filter-values-wrap scrollable">
			<div class="filter-opt ${!task.completed_by ? "on" : ""}" data-act="savecompletedby" data-id="${task.id}" data-value="">Unassigned</div>
			${TaskLeadOptions.map(function (u) {
					return `<div class="filter-opt ${task.completed_by === u ? "on" : ""}" data-act="savecompletedby" data-id="${task.id}" data-value="${u}">${u}</div>`;
				}).join("")}
		</div>
	</div>
	`;
			}
			else {
				menuHtml = `
			<div class="d-menu" >
			${renderTaskMenuCards(task)}
    <div class="d-act" data-act="close"><div>${frappe.utils.icon("close", "sm")}</div> Close</div>
  </div>
			`;
			}
		}
		return `
	<div class="d-row lvl-task ${task.id === state.selectedTask ? 'sel' : ''}" data-task-id=${task.id}>
	<div style="display:flex; flex-direction:column; gap:6px; flex:1">
		<div style="display:flex; flex-direction:column; gap:4px">
			<div style="font-weight:500">${task.name}</div>
			<div class="d-meta" style="font-weight:400; margin-bottom:6px">${testProjects.find(function (p) {
			return p.id === task.project
		})?.name || task.project}
			</div>
			<div style="display:flex; gap:4px; flex-wrap:wrap">
				${chip(task.stage)}
				${chip(task.status)}
				${urg(task.urgency)}
			</div>
			<div style="display:flex;gap:4px;flex-wrap:wrap">
			${renderModuleCards(task.module)}
			</div>
		</div>

		<div class="d-own-row">
			<span class="d-own">${task.div} Lead:</span>
			${renderLeads(task.lead)}
		</div>

		<div class="d-meta">
			${task.due ? fmtDate(task.due) : "No Due date"} · ${task.status === "Completed" ? `<span style="color:var(--text-success)">Completed</span>` : dueChip("Task", task.due)}
		</div>

		${task.creation ? `
		<div class="d-meta" style="color:var(--text-accent)">
		<span style="display:inline-flex; width:12px; height:12px">${frappe.utils.icon("clock", "xs")}</span>	
		${task.status} since ${fmtDate(task.creation)}
		</div>
		` : ""}

		${task.status === "Completed" ? `
		<div style="display:flex; gap:6px; margin-top:8px; padding-top:8px; border-top:1px solid var(--border); flex-wrap:wrap">
			<button class="btn-completed-card" data-act="setcompletedon" data-id="${task.id}">
				<span style="color:var(--text-success)">✓</span>
				Completed on: ${task.completed_on ? fmtDate(task.completed_on) : "Set date"}
			</button>
			<button class="btn-completed-card" data-act="setcompletedby" data-id="${task.id}">
				${frappe.utils.icon("user-check", "xs")} Completed by: ${task.completed_by ? task.completed_by : "Set person"}
			</button>
		</div>
		` : ""}

		<div style="display:flex; gap:6px; margin-top:6px; padding-top:6px; border-top:1px solid var(--border)">
			${renderReactions(task)}
		</div>
	</div>
	<button class="d-dots" data-act="dots" data-id="${task.id}">${frappe.utils.icon("dot-vertical", "sm")}</button>
	<button class="d-info" data-act="opendrawer" data-type="Task" data-id="${task.id}">${frappe.utils.icon("info", "sm")}</button>
	${menuHtml}
	</div>
	`;
	}
	var todo_menu_actions = [
		{ act: "details", icon: "info", label: "Details & activity" },
		{ act: "gotostatus", icon: "circle-dot", label: "Change status" },
		{ act: "assignto", icon: "user-plus", label: "Assign" },
		{ act: "gotourgency", icon: "flame", label: "Set Urgency" },
		{ act: "gotodue", icon: "calendar-days", label: "Change Due date" },
		{ act: "copylink", icon: "copy", label: "Copy link", doc: "ToDo" },
		{ act: "sendslackdm", icon: "send", label: "Send to Slack direct message", doc: "ToDo" },
		{ act: "sendslackchannel", icon: "send", label: "Send to Slack Channel", doc: "ToDo" },
		{ act: "sendwhatsapp", icon: "send", label: "Send to WhatsApp", doc: "ToDo" }
	];
	function renderToDoMenuOptions(todo) {
		return todo_menu_actions.map(function (action) {
			var docAttr = action.doc ? ` data-doc="${action.doc}"` : "";
			return `
			<div class="d-act" data-act=${action.act} data-id="${todo.id}" ${docAttr}><div>${frappe.utils.icon(action.icon, "sm")}</div>${action.label}</div>
			`;
		}).join("")
	}
	function renderToDoCard(todo) {
		var icon = todo.done ? "✓" : "○";
		var textStyle = todo.done ? "text-decoration:line-through;color:var(--text-muted)" : "";
		var menuHtml = "";
		if (state.menu && state.menu.id === todo.id) {
			if (state.menu.mode === "status") {
				menuHtml = `
			<div class = "d-menu" >
				<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Status</div>
				<div style="display:flex; flex-wrap:wrap; gap:6px">
				<div class="d-opt" data-act="setstatus" data-id="${todo.id}" data-value="Open">Open</div>
				<div class="d-opt" data-act="setstatus" data-id="${todo.id}" data-value="Closed">Closed</div>
				<div class="d-opt" data-act="setstatus" data-id="${todo.id}" data-value="Cancelled">Cancelled</div>
				</div>
				</div>
			`;
			}
			else if (state.menu.mode === "assignto") {
				menuHtml = `
			<div class="d-menu" >
			<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Assign To</div>
			<div style="display:flex; flex-wrap:wrap; gap:6px">
			${OptionalHtml}
			</div>
			</div>
	`;
			}
			else if (state.menu.mode === "changeurg") {
				menuHtml = `
			<div class="d-menu" >
					<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Set Urgency🔥</div>
					<div style="display:flex; flex-wrap:wrap; gap:6px">
					<div class = "d-opt"  data-act="seturg" data-id="${todo.id}" data-value="Emergency">Emergency</div>
					<div class = "d-opt" data-act="seturg" data-id="${todo.id}" data-value="Urgent">Urgent</div>
					<div class = "d-opt" data-act="seturg" data-id="${todo.id}" data-value="Normal">Normal</div>
					<div class = "d-opt" data-act="seturg" data-id="${todo.id}" data-value="Low">Low</div>
					</div>
					</div>
			`;
			}
			else if (state.menu.mode === "changedue") {
				menuHtml = `
	<div class="d-menu">
		<div class="due-date-picker-wrapper">
			<div class="due-date-label">Due date</div>
			<div class="due-date-input-row">
				<input type="text" data-act="changeduedate" id="due-date-input" data-id="${todo.id}"
					value="${frappe.datetime.str_to_user(todo.due)}"
					placeholder="Select Date"
					style="width:auto; max-width:180px; padding:6px 10px" autocomplete="off" readonly/>
			</div>
			<div id="due-date-calendar-container"></div>
			<div class="due-date-footer">
				<button class="btn btn-default btn-sm" data-doc="todos" data-act="close">Cancel</button>
				<button class="btn btn-primary btn-sm" data-act="savedue" data-id="${todo.id}">Save</button>
			</div>
		</div>
	</div>
	`;
			}
			else {
				menuHtml = `
			<div class="d-menu" >
			${(renderToDoMenuOptions(todo))}
    <div class="d-act" data-act="close"><div style="display:inline-flex">${frappe.utils.icon("close", "sm")}</div> Close</div>
  </div>
			`;
			}
		}
		return `
			<div class="d-row lvl-todo ${todo.id === state.selectToDo ? 'sel' : ''}" data-todo-id=${todo.id}>
				${icon}
			<div style="display:flex; flex-direction:column; gap:6px; flex:1">
			<div>
				<div style="${textStyle}">${todo.name}</div>
				${chip(todo.status)}
				${urg(todo.urgency)}
				${chip(todo.priority)}
			</div>
			<div style="display:flex; gap:4px; flex-wrap:wrap">
				${renderModuleCards(todo.module)}
			</div>
				<div class="d-own">Assigned To · ${renderLeads(todo.who)}</div>
							<div style="margin-top:8px">
			<div class="d-meta" >${frappe.utils.icon("calendar-days")} ${fmtDate(todo.due)} · ${dueChip("ToDo", todo.due)}</div></div>
				<div style="display:flex; gap:6px">${renderReactions(todo)}</div>
			</div>
			<button class="d-dots" data-act="dots" data-id="${todo.id}">${frappe.utils.icon("dot-vertical", "sm")}</button>
			<button class="d-info" data-act="opendrawer" data-type="ToDo" data-id="${todo.id}">${frappe.utils.icon("info", "sm")}</button>
			${menuHtml}
			</div>
			`;

	}
	function renderModuleCards(module) {
		if (!module) {
			return `<div class="d-meta">No module assigned.</div>`;
		}
		// var inScope = !!module.in_scope;
		var color = "var(--text-success)";
		var bg = "var(--bg-success)";
		return `
			<div class="d-chip" style="color:${color}; background:${bg}; border:0.5px solid ${color}">
				${module}
			</div>
		`;
	}
	function renderProjectsColumn(projects) {
		return projects.map(renderProjectCard).join("")
	}
	function renderTasksColumn(tasks) {
		return tasks.map(renderTaskCard).join("")
	}
	function renderToDosColumn(todos) {
		return todos.map(renderToDoCard).join("")
	}
	function ppct(project) { return project.percent || 0; }

	function pct(task) { return task.percent || 0; }
	async function loadProjects() {
		var rows = await frappe.xcall("implementor.api.get_projects")
		testProjects = rows.map(function (r) {
			return {
				id: r.name,
				name: r.title,
				client: r.client,
				status: r.del_status,
				pm: r.pm,
				percent: r.percent,
				description: r.description,
				due: r.deadline,
				reactions: r.reaction_counts || {},
				activity: r.activity,
				comments: r.comments,
				attachments: r.attachments,
				slack_channel_id: r.slack_channel_id,
				percent_complete: r.percent_complete,
				whatsapp_channel_id: r.whatsapp_channel_id
			}
		});
		showFilteredProjects();

	}
	async function loadTodos(taskId, projectId) {
		var rows = await frappe.xcall("implementor.api.get_todos", { task: taskId, project: projectId });
		testTodos = rows.map(function (r) {
			return {
				id: r.name,
				task: r.task || taskId,
				name: r.title,
				who: r.assignee,
				done: !!r.done,
				status: r.status || "Open",
				priority: r.priority || "Low",
				urgency: r.urgency,
				due: r.deadline,
				reactions: r.reaction_counts || {},
				comments: r.comments,
				attachments: r.attachments,
				activity: r.activity,
				description: r.title,
				slack_channel_id: r.slack_channel_id,
				whatsapp_channel_id: r.whatsapp_channel_id,
				module: r.imp_module
			};
		});
		showToDosForSelectedTasks();
		return testTodos;
	}
	async function loadTasks(projectId) {
		var rows = await frappe.xcall("implementor.api.get_tasks", { project: projectId })
		testTasks = rows.map(function (r) {
			return {
				id: r.name,
				completed_on: r.completed_on,
				completed_by: r.completed_by,
				project: r.project || projectId,
				name: r.title,
				description: r.description,
				stage: r.stage,
				div: r.division,
				assigned_to: r.assigned_to,
				status: r.status,
				lead: r.lead,
				urgency: r.urgency,
				percent: r.percent,
				due: r.deadline,
				div: r.division,
				activity: r.activity,
				comments: r.comments,
				creation: r.started_on,
				attachments: r.attachments,
				reactions: r.reaction_counts || {},
				slack_channel_id: r.slack_channel_id,
				whatsapp_channel_id: r.whatsapp_channel_id,
				module: r.imp_module
			};
		});
		showFilteredTasks();

	}
	async function get_deliv_options() {
		DeliverystatusOptions = await frappe.xcall("implementor.api.get_project_status_options");
		divisions = await frappe.xcall("implementor.api.get_div_options")

	}
	function loadFlatpickr(callback = () => { }) {
		if (window.implFlatpickr) { callback(); return; }
		var css = document.createElement("link");
		css.rel = "stylesheet";
		css.href = "https://cdn.jsdelivr.net/npm/flatpickr/dist/flatpickr.min.css";
		document.head.appendChild(css);

		var script = document.createElement("script");
		script.src = "https://cdn.jsdelivr.net/npm/flatpickr";
		script.onload = function () {
			window.implFlatpickr = window.flatpickr;
			callback();
		};
		document.head.appendChild(script);
	}
	async function loadTaskLeadOptions() {
		var users = await frappe.xcall("implementor.api.get_users", {});
		TaskLeadOptions = users.map(function (u) {
			return u.name
		})
		assignees = TaskLeadOptions
		// persons = TaskLeadOptions
	}
	var testProjects = []
	var testTasks = [];
	var testTodos = []
	async function init() {
		await get_deliv_options();
		await loadProjects();
		tasks = await loadTasks();
		todos = await loadTodos();
		await loadNotifCount();
		await loadDashboard();
		renderNotifyPanel();
		renderEmergencyPanel();
		await loadTaskLeadOptions();
		await get_todo_status_options();
		loadFlatpickr();
		renderPersonFilter();
	}
	init();
}


