frappe.pages['implementor_board'].on_page_load = function (wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'None',
		single_column: true
	});
	var dashboardData = null;
	var currentUser = frappe.session.user;
	page.set_title('Implementor');
	var state = {
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
		var due_date = new Date(dueDateString);
		var mesPerDay = 1000 * 60 * 60 * 24;
		var diff = due_date - today;
		return Math.round(diff / mesPerDay)
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

	function showFilteredProjects() {
		var filtered = testProjects.filter(function (project) {
			var mineOnly = !state.mineOnly || project.pm === currentUser
			var match_pct = ppct(project) >= state.minPct && ppct(project) <= state.maxPct;
			var match_name = state.namedFilter === "" || project.name.toLowerCase().includes(state.namedFilter.toLowerCase());
			var match_person_name = state.personFilter === "" || (project.pm || "").toLowerCase().includes(state.personFilter.toLowerCase());
			return mineOnly && match_pct && match_name && match_person_name;
		}
		)
		var sorted = sortedBy(filtered);
		if (state.selectedProject) {
			var selectedIndex = sorted.findIndex(function (p) {
				return p.id === state.selectedProject;
			})
			if (selectedIndex > 0) {
				var selectedProject = sorted[selectedIndex];
				sorted.splice(selectedIndex, 1);
				sorted.unshift(selectedProject)
			}
		}
		document.getElementById("project-count").textContent = sorted.length + " projects shown";
		document.getElementById("d-projects").innerHTML = renderProjectsColumn(sorted);

	}
	function showFilteredTasks() {
		var filtered = testTasks.filter(function (task) {
			var mineOnly = !state.mineOnly || task.assigned_to === currentUser
			var match_project = state.selectedProject === null || task.project == state.selectedProject;
			var match_pct = pct(task) >= state.minPct && pct(task) <= state.maxPct;
			var match_name = state.namedFilter === "" || task.name.toLowerCase().includes(state.namedFilter.toLowerCase());
			var match_urgency = state.urgencyFilter === "" || task.urgency == state.urgencyFilter;
			var match_person = state.personFilter === "" || task.assigned_to && String(task.assigned_to).toLowerCase().includes(state.personFilter.toLowerCase());
			return match_pct && mineOnly && match_project && match_name && match_urgency && match_person;
		});
		var sorted = sortedBy(filtered);
		document.getElementById("d-tasks").innerHTML = renderTasksColumn(sorted);

	}
	function showToDosForSelectedTasks() {
		var filtered = testTodos.filter(function (todo) {
			var mineOnly = !state.mineOnly || todo.who === currentUser
			var todo_filtered = state.selectedTask === null || todo.task == state.selectedTask;
			var match_name = state.namedFilter === "" || todo.description.toLowerCase().includes(state.namedFilter.toLowerCase());
			var match_person = state.personFilter === "" || (todo.who || "").toLowerCase().includes(state.personFilter.toLowerCase());
			var match_urgency = state.urgencyFilter === "" || todo.urgency == state.urgencyFilter;
			return match_name && mineOnly && todo_filtered && match_person && match_urgency;
		});
		var sorted = sortedBy(filtered);
		document.getElementById("d-todos").innerHTML = renderToDosColumn(sorted);
	}

	function selectProject(id) {
		state.selectedProject = id;
		state.selectedTask = null;
		loadTasks(id);
		loadTodos(undefined, id);
		showFilteredProjects();
	};
	function selectTask(id) {
		state.selectedTask = id;
		loadTodos(id);
	};
	async function selectToDo(id) {
		var todo = testTodos.find(function (t) {
			return t.id === id;
		});
		todo.done = !todo.done;
		showToDosForSelectedTasks();
		var result = await frappe.xcall("implementor.api.toggle_todo_done", { todo: id });
		var task = testTasks.find(function (t) { return t.id === result.task; });
		if (task) task.percent = result.task_percent;
		var project = testProjects.find(function (p) { return p.id === result.project; });
		if (project) project.percent = result.project_percent;

		showFilteredTasks();
		showFilteredProjects();
	};
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

		var deadlineText = isEmergency ? (item.imp_escalated ? "Escalated" : "Emergency") : dueChip(item.deadline);
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
	var sampleDeadlinesSoon = [
		{
			name: "TASK-2026-00021",
			doctype: "Task",
			title: "Inventory data migration",
			imp_deadline: "2026-07-26",
			escalated: 0
		},
		{
			name: "TASK-2026-00014",
			doctype: "Task",
			title: "Bank gateway integration",
			imp_deadline: "2026-07-30",
			escalated: 1
		},
		{
			name: "TASK-2026-00014",
			doctype: "Task",
			title: "Bank gateway integration",
			imp_deadline: "2026-07-30",
			escalated: 1
		}
	];

	var sampleEmergencies = [
		{
			name: "TASK-2026-00007",
			doctype: "Task",
			title: "Production CSID onboarding",
			imp_deadline: "2026-07-25",
			escalated: 1
		},
		{
			name: "TASK-2026-00007",
			doctype: "Task",
			title: "Production CSID onboarding",
			imp_deadline: "2026-07-25",
			escalated: 1
		},
		{
			name: "TASK-2026-00019",
			doctype: "Task",
			title: "ZATCA compliance validation failure",
			imp_deadline: "2026-07-24",
			escalated: 0
		}

	];
	function oneStatusBar(progressState, name, count, max) {
		var pct = Math.round((count / max) * 100);
		return `
		<div class="dbar-row">
		<div class="dbar-lbl">${name}</div>
		<div class="dbar-trk"><div class="dbar-fill" style="width:${pct}%"></div></div>
		<div style="width:36px; text-align:right; color:var(--text-secondary)">${!progressState ? count : pct + "%"}</div>
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
		var cardsHtml = [
			metricCard("Projects", d.projects),
			metricCard("Tasks", d.tasks),
			metricCard("Avg Process", d.avg_progress + "%"),
			metricCard("Due ≤ 7 days ", d.due_7d),
			metricCard("Overdue", d.overdue, true),
			metricCard("Escalated", d.escalated, true),
		].join("")
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
			<div class="dw-sec"><div class="dw-lbl">PROGRESS BY STAGE (all projects)</div>
			${statusBarSection(true, d.stage_avg_progress)}</div>
			<div class="dw-sec"><div class="dw-lbl">OPEN TASKS BY DIVISION</div>
			${statusBarSection(false, d.by_division)}</div>
		`;
	}

	async function loadDashboard() {
		dashboardData = await frappe.xcall("implementor.api.dashboard_summary");
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
				<div class="legend"><span class="dot" style="background:var(--lvl-task)"></span> Task</div>
				<div class="legend"><span class="dot" style="background:var(--lvl-todo)"></span> To-do</div>
			</div>
			<div style="display:flex; align-items:center; gap:10px">
			<div style="position:relative">
			<button id="btn-add" class="d-menu">${frappe.utils.icon("plus", "xs")} Add</button>
			<div id="add-menu" class="add-popover" style="display:none;right:0;"></div>
			</div>
			</div>
		</div>
		<div class="topbar">
		<div style="display:flex; gap:12px; padding:16px 16px 12px; flex-wrap:wrap">
		<input id="f-name" placeholder="Search project name" />
		<select id ="f-urgency">
			<option value="">Any urgency</option>
			<option value="Emergency">Emergency</option>
			<option value="Urgent">Urgent</option>
			<option value="Normal">Normal</option>
			<option value="Low">Low</option>
		</select>
		<input id="f-person" placeholder="Person" />
		<input id="f-min" type = "number" placeholder="0"/>
		<input id="f-max" type = "number" placeholder="100"/>
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
			</div>
			<div id="d-projects"></div>
			</div>
			<div>
				<div id="h-tasks" class="d-hd">
				<div style="display:inline-flex">${frappe.utils.icon("file", "sm")}</div>
				Tasks
				</div>
				<div id="d-tasks"></div>
			</div>
			<div>
				<div id="h-todos" class="d-hd">
				<div style="display:inline-flex">${frappe.utils.icon("circle-check-big", "sm")}</div>
				To-dos
				</div>
				<div id="d-todos"></div>
			</div>
		</div>
		<div id="drawer" style="display:none;"></div>
		<div id="dashboard-view" style="display:none; padding:16px;">
		</div>
		</div>
	  `);
	function updateView() {
		document.getElementById("btn-board").classList.toggle("on", state.view === "board");
		document.getElementById("btn-dashboard").classList.toggle("on", state.view === "dashboard");
		document.querySelector(".topbar").style.display = state.view === "board" ? "block" : "none";
		document.querySelector(".grid").style.display = state.view === "board" ? "grid" : "none";
		document.getElementById("dashboard-view").style.display = state.view === "dashboard" ? "block" : "none";

	}
	document.getElementById("btn-board").addEventListener("click", function (e) {
		state.view = "board";
		updateView();
	});
	document.getElementById("btn-dashboard").addEventListener("click", function (e) {
		state.view = "dashboard";
		loadDashboard().then(function () { updateView(); });
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
	}
	document.getElementById("add-menu").addEventListener("click", function (e) {
		var newproject = e.target.closest("[data-act='newproject']");
		if (newproject) {
			state.add = false;
			renderAddMenu();
			frappe.new_doc("Project");
			return
		};
		var newtask = e.target.closest("[data-act='newtask']");
		if (newtask) {
			state.add = false;
			renderAddMenu();
			frappe.new_doc("Task");
			return
		};
		var newtodo = e.target.closest("[data-act='newtodo']");
		if (newtodo) {
			state.add = false;
			renderAddMenu();
			frappe.new_doc("ToDo");
			return
		};
	});

	document.getElementById("d-projects").addEventListener("click", function (e) {
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
		var dots = e.target.closest("[data-act='dots']")
		if (dots) {
			var id = dots.getAttribute("data-id");
			state.selectedProject = id;
			state.menu = (state.menu && state.menu.id === id) ? null : { id: id, mode: null };
			showFilteredProjects();
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
	document.getElementById("d-tasks").addEventListener("click", function (e) {
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
		var details = e.target.closest("[data-act='details']");
		if (details) {
			id = details.getAttribute("data-id");
			state.drawer = { id: id, type: "Task" }
			state.menu = null;
			renderDrawer();
			showFilteredTasks();
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
			state.menu.mode = "changeurg";
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
		if (state.menu != null && !e.target.closest(".d-menu") && !e.target.closest("[data-act='dots']")) {
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
	document.getElementById("f-person").addEventListener("input", function (e) {
		state.personFilter = e.target.value;
		showFilteredProjects()
		showFilteredTasks()
		showToDosForSelectedTasks()
	});
	document.getElementById("f-min").addEventListener("input", function (e) {
		state.minPct = Number(e.target.value) || 0;
		showFilteredProjects();
		showFilteredTasks();
	});
	document.getElementById("f-max").addEventListener("input", function (e) {
		state.maxPct = Number(e.target.value) || 100;
		showFilteredProjects();
		showFilteredTasks();
	});
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
		state.maxPct = 100;
		state.minPct = 0;
		state.namedFilter = "";
		state.personFilter = "";
		state.mineOnly = false;
		state.sortFilter = "";
		state.urgencyFilter = "";
		document.getElementById("f-name").value = "";
		document.getElementById("f-urgency").value = "";
		document.getElementById("f-person").value = "";
		document.getElementById("f-min").value = "";
		document.getElementById("f-max").value = "";
		document.getElementById("f-sort").value = "";
		document.getElementById("f-mine").textContent = "My work";
		showFilteredProjects();
		showFilteredTasks();
		showToDosForSelectedTasks();

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

		return list + `
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
			<div class="d-meta" >${frappe.utils.icon("calendar-days")} ${fmtDate(project.due)} · ${dueChip(project.due)}</div></div>
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
						${task.div} Assigned To: ${renderLeads(task.assigned_to)}
					</div>
				</div>
				<div style="margin-top:8px">
					<div class="d-meta">${frappe.utils.icon("calendar-days")} ${fmtDate(task.due)} 💠 ${dueChip(task.due)} · ${task.status} · ${pct(task)}%</div>
					<div style="margin-top:4px">
						<div class="d-meta" style="color:var(--text-accent)">
							${frappe.utils.icon("clock", "xs")} ${task.status} since ${fmtDate(task.creation)} ${renderLeads(task.assigned_to)}
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
      <div class="d-meta">${frappe.utils.icon("calendar-days", "xs")} ${fmtDate(todo.due)} · ${dueChip(todo.due)}</div>
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
			var errBody = await response.json();
			var friendlyMessage = "Upload failed";
			try {
				if (errBody._server_messages) {
					var messages = JSON.parse(errBody._server_messages);       // first parse: array of strings
					var firstMessage = JSON.parse(messages[0]);                 // second parse: the actual object
					friendlyMessage = firstMessage.message;
				}
			} catch (e) {
				friendlyMessage = "Parsing Failed"
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
		var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
		var d = new Date(dueDateSting);
		return d.getDate() + " " + months[d.getMonth()];
	}
	function renderLeads(lead) {
		var names = Array.isArray(lead) ? lead : (lead ? String(lead).split(",") : []);
		names = names.map(function (n) { return n.trim(); });
		names = names.filter(function (name, i) { return names.indexOf(name) === i; });

		if (names.length === 0) {
			return `<span style = "color:var(--text-muted)" > Unassigned</span>`;
		}

		return names.map(function (name) {
			return `<span class="d-chip" style = "background:var(--surface-1); color:var(--text-secondary)" > ${frappe.utils.icon("user", "xs")} ${name}</span>`;
		}).join(" ");
	}
	function dueChip(dueDateString) {
		var days = remDays(dueDateString);
		if (days > 0) return `<span> ${days}d left</span>`;
		if (days === 0) return `<span style = "color:orange" > Due today</span>`;
		return `<span style = "color:var(--text-danger)" > ${Math.abs(days)}d overdue</span>`;

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
			"Active": ["var(--text-accent)", "var(--bg-accent)"],        // ADDED — main "in progress" state
			"Config": ["var(--text-accent)", "var(--bg-accent)"],
			"Data Migration": ["var(--text-accent)", "var(--bg-accent)"],
			"Integration": ["var(--text-warning)", "var(--bg-warning)"],
			"UAT": ["var(--text-warning)", "var(--bg-warning)"],
			"Training": ["var(--text-success)", "var(--bg-success)"],
			"Go-Live": ["var(--text-danger)", "var(--bg-danger)"],
			"Hypercare": ["var(--text-warning)", "var(--bg-warning)"],
			"Closed": ["var(--text-muted)", "var(--surface-1)"],
			"Done": ["var(--text-success)", "var(--bg-success)"],        // ADDED — completed, matches "Completed"/"Training"
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
				menuHtml = `
			<div class = "d-menu" >
				<div class="d-hd" style="background:transparent; border:none; padding:0 0 8px">Status</div>
				<div style="display:flex; flex-wrap:wrap; gap:6px">
				<div class="d-opt" data-act="setstatus" data-id="${project.id}" data-value="Discovery">Discovery</div>
				<div class="d-opt" data-act="setstatus" data-id="${project.id}" data-value="Active">Active</div>
				<div class="d-opt" data-act="setstatus" data-id="${project.id}" data-value="Go-Live">Go-Live</div>
				<div class="d-opt" data-act="setstatus" data-id="${project.id}" data-value="Hypercare">Hypercare</div>
				<div class="d-opt" data-act="setstatus" data-id="${project.id}" data-value="Closed">Closed</div>
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
			else {
				menuHtml = `
			<div class="d-menu" >
    <div class="d-act" data-act="details" data-id="${project.id}"><div>${frappe.utils.icon("info", "sm")}</div> Details & activity</div>
    <div class="d-act" data-act="gotostatus" data-id="${project.id}"><div>${frappe.utils.icon("circle-dot", "sm")}</div> Change status</div>
    <div class="d-act" data-act="changepm" data-id="${project.id}"><div>${frappe.utils.icon("user-check", "sm")}</div> Change project manager</div>
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
			<div class="d-meta">${fmtDate(project.due)} · ${dueChip(project.due)}</div>
			${prog(ppct(project))}
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
			else {
				menuHtml = `
			<div class="d-menu" >
    <div class="d-act" data-act="details" data-id="${task.id}"><div>${frappe.utils.icon("info", "sm")}</div> Details & activity</div>
    <div class="d-act" data-act="gotostatus" data-id="${task.id}"><div>${frappe.utils.icon("circle-dot", "sm")}</div> Change status</div>
    <div class="d-act" data-act="gotodivision" data-id="${task.id}"><div>${frappe.utils.icon("tag", "sm")}</div> Change Division</div>
    <div class="d-act" data-act="gotourgency" data-id="${task.id}"><div>${frappe.utils.icon("flame", "sm")}</div> Set Urgency</div>
    <div class="d-act" data-act="close"><div>${frappe.utils.icon("close", "sm")}</div> Close</div>
  </div>
			`;
			}
		}
		return `
			<div class="d-row lvl-task ${task.id === state.selectedTask ? 'sel' : ''}" data-task-id=${task.id}>
			<div style="display:flex; flex-direction:column; gap:6px; flex:1">
				<div>
				<div style="font-weight:500">${task.name}</div>
				${chip(task.stage)}
				${chip(task.status)}
				${urg(task.urgency)}
				</div>
				<div class="d-own-row">
				<span class="d-own">${task.div} Lead:</span>
				${renderLeads(task.assigned_to)}
				</div>
				<div class="d-meta">${fmtDate(task.due)} 💠 ${dueChip(task.due)}</div>
				<div class="d-meta" style="color:var(--text-accent)">
				 ${task.status} since ${fmtDate(task.creation)}
				</div>
				${prog(pct(task))}
				<div style="display:flex; gap:6px">${renderReactions(task)}</div>
			</div>
			<button class="d-dots" data-act="dots" data-id="${task.id}">${frappe.utils.icon("dot-vertical", "sm")}</button>
			<button class="d-info" data-act="opendrawer" data-type="Task" data-id="${task.id}">${frappe.utils.icon("info", "sm")}</button>
			${menuHtml}
			</div>
			`;
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
			else {
				menuHtml = `
			<div class="d-menu" >
    <div class="d-act" data-act="details" data-id="${todo.id}"><div style="display:inline-flex">${frappe.utils.icon("info", "sm")}</div> Details & activity</div>
    <div class="d-act" data-act="gotostatus" data-id="${todo.id}"><div style="display:inline-flex">${frappe.utils.icon("circle-dot", "sm")}</div> Change status</div>
    <div class="d-act" data-act="assignto" data-id="${todo.id}"><div style="display:inline-flex">${frappe.utils.icon("user-plus", "sm")}</div> Assign</div>
    <div class="d-act" data-act="gotourgency" data-id="${todo.id}"><div style="display:inline-flex">${frappe.utils.icon("flame", "sm")}</div> Set Urgency</div>
    <div class="d-act" data-act="close"><div style="display:inline-flex">${frappe.utils.icon("close", "sm")}</div> Close</div>
  </div>
			`;
			}
		}
		return `
			<div class="d-row lvl-todo" data-todo-id=${todo.id}>
				${icon}
			<div style="display:flex; flex-direction:column; gap:6px; flex:1">
			<div>
				<div style="${textStyle}">${todo.name}</div>
				${chip(todo.status)}
				${urg(todo.urgency)}
				${chip(todo.priority)}
			</div>
				<div class="d-own">Assigned To · ${renderLeads(todo.who)}</div>
				<div style="display:flex; gap:6px">${renderReactions(todo)}</div>
			</div>
			<button class="d-dots" data-act="dots" data-id="${todo.id}">${frappe.utils.icon("dot-vertical", "sm")}</button>
			<button class="d-info" data-act="opendrawer" data-type="ToDo" data-id="${todo.id}">${frappe.utils.icon("info", "sm")}</button>
			${menuHtml}
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
				status: r.status,
				pm: r.pm,
				percent: r.percent,
				description: r.description,
				due: r.deadline,
				reactions: r.reaction_counts || {},
				activity: r.activity,
				comments: r.comments,
				attachments: r.attachments
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
				description: r.title
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
				project: r.project || projectId,
				name: r.title,
				description: r.description,
				stage: r.stage,
				div: r.division,
				assigned_to: r.assigned_to,
				status: r.status,
				urgency: r.urgency,
				percent: r.percent,
				due: r.deadline,
				div: r.division,
				activity: r.activity,
				comments: r.comments,
				creation: r.started_on,
				attachments: r.attachments,
				reactions: r.reaction_counts || {},
			};
		});
		showFilteredTasks();

	}
	async function cretae_dummy_data() {
		var res = await frappe.xcall("implementor.api.seed_dummy_projects")

	}
	var testProjects = []
	var testTasks = [];
	var testTodos = []
	async function init() {
		await loadProjects();
		tasks = await loadTasks();
		todos = await loadTodos();
	}
	init();
}


