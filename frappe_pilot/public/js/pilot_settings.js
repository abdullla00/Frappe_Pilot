const PILOT_ENGLISH_LANGUAGE = "en";

function _disable_api_key_password_checks(frm) {
	const grid = frm.get_field("llm_providers");
	if (!grid || !grid.grid) return;

	const disableGridRow = (grid_row) => {
		const field = grid_row.on_grid_fields_dict?.api_key;
		if (field && typeof field.disable_password_checks === "function") {
			field.disable_password_checks();
		}
	};

	grid.grid.grid_rows.forEach(disableGridRow);
	if (!grid._pilot_api_key_hooks) {
		grid._pilot_api_key_hooks = true;
		$(frm.wrapper).on("grid-row-render.pilot-api-key", (e, grid_row) => {
			if (grid_row) disableGridRow(grid_row);
		});
	}
}

frappe.ui.form.on("Pilot Settings", {
	refresh(frm) {
		_disable_api_key_password_checks(frm);
		_render_languages_help(frm);
		_render_navigation_help(frm);
		_inject_llm_grid_styles();
		_ensure_english_language_row(frm);
		_setup_enabled_languages_grid(frm);
		_setup_llm_providers_grid(frm);
		_refresh_llm_provider_ui(frm);
		_setup_llm_status_poll(frm);
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "frappe_pilot.api.config.test_api_connection",
				freeze: true,
				freeze_message: __("Testing API connection…"),
				callback(r) {
					_show_llm_test_results(r.message);
					_refresh_llm_provider_ui(frm);
				},
			});
		});
	},
	llm_failover_mode() {
		_refresh_llm_provider_ui(cur_frm);
	},
	llm_providers(frm) {
		_schedule_llm_grid_sync(frm);
	},
	llm_providers_add(frm) {
		_normalize_llm_priorities(frm);
		_schedule_llm_grid_sync(frm);
	},
	llm_providers_remove(frm) {
		_schedule_llm_grid_sync(frm);
	},
	llm_providers_on_form_rendered(frm) {
		_schedule_llm_grid_sync(frm);
	},
	auto_navigate(frm) {
		_render_navigation_help(frm);
	},
	close_sidebar_on_navigate(frm) {
		_render_navigation_help(frm);
	},
	after_save(frm) {
		if (window.FrappePilot && typeof window.FrappePilot.refreshConfig === "function") {
			window.FrappePilot.refreshConfig();
		}
		_refresh_llm_provider_ui(frm);
	},
	before_enabled_languages_remove(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.language === PILOT_ENGLISH_LANGUAGE) {
			frappe.throw(__("English is required in Pilot and cannot be removed."));
		}
	},
});

frappe.ui.form.on("Pilot LLM Provider", {
	llm_provider(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		_schedule_llm_grid_sync(frm);
		if (!row || !row.llm_provider || row.model) return;
		frappe.db.get_value("LLM Provider", row.llm_provider, "default_model").then((r) => {
			if (r.message && r.message.default_model) {
				frappe.model.set_value(cdt, cdn, "model", r.message.default_model).then(() => {
					_schedule_llm_grid_sync(frm);
				});
			}
		});
	},
	enabled() {
		_schedule_llm_grid_sync(cur_frm);
	},
	priority() {
		_normalize_llm_priorities(cur_frm);
	},
	row_label() {
		_schedule_llm_grid_sync(cur_frm);
	},
	model() {
		_schedule_llm_grid_sync(cur_frm);
	},
	form_render(frm) {
		_schedule_llm_grid_sync(frm);
	},
});

function _inject_llm_grid_styles() {
	let style = document.getElementById("pilot-llm-grid-styles");
	if (!style) {
		style = document.createElement("style");
		style.id = "pilot-llm-grid-styles";
		document.head.appendChild(style);
	}
	style.textContent = `
		.pilot-llm-providers-grid .grid-row {
			transition: background-color 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
		}
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active > .data-row,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active .data-row {
			background-color: var(--bg-green, #edf7ed) !important;
			box-shadow: inset 4px 0 0 var(--green-500, #28a745);
		}
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited > .data-row,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited .data-row {
			background-color: var(--bg-red, #fde8e8) !important;
			box-shadow: inset 4px 0 0 var(--red-500, #e03636);
		}
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active .data-row .row-check,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active .data-row .row-index,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active .data-row .grid-static-col,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited .data-row .row-check,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited .data-row .row-index,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited .data-row .grid-static-col {
			background-color: transparent !important;
		}
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active .static-area,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited .static-area,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-active .like-disabled-input,
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-limited .like-disabled-input {
			background-color: transparent !important;
		}
		.pilot-llm-providers-grid .grid-row.pilot-llm-row-disabled {
			opacity: 0.5;
		}
		.pilot-llm-providers-grid .grid-body [data-fieldname="limited"] .static-area,
		.pilot-llm-providers-grid .grid-body [data-fieldname="limited"] .control-value {
			color: var(--red-600);
			font-weight: 600;
		}
	`;
}

function _format_retry_sec(sec) {
	const n = parseInt(sec, 10);
	if (!n || n < 1) return "";
	if (n >= 3600) return Math.ceil(n / 3600) + "h";
	if (n >= 60) return Math.ceil(n / 60) + "m";
	return n + "s";
}

function _format_limited_field(state) {
	if (!state || state.status !== "rate_limited") return "";
	if (state.retry_in_sec) {
		return "~" + _format_retry_sec(state.retry_in_sec);
	}
	return __("Yes");
}

function _find_row_state(doc, states) {
	if (!doc || !states) return null;
	if (states[doc.name]) return states[doc.name];

	const priority = parseInt(doc.priority, 10) || 0;
	const provider = (doc.llm_provider || "").trim();
	const row_label = (doc.row_label || "").trim();
	if (!priority || !provider) return null;

	for (const state of Object.values(states)) {
		if (parseInt(state.priority, 10) !== priority) continue;
		const state_provider = (state.provider || "").trim();
		if (state_provider && state_provider !== provider) continue;
		if (row_label && state.row_label && state.row_label !== row_label) continue;
		return state;
	}
	return null;
}

function _schedule_llm_grid_sync(frm) {
	if (!frm) return;
	const run = () => _apply_llm_grid_state(frm);
	[0, 120, 300, 600].forEach((delay, idx) => {
		const key = `_pilot_llm_sync_timer_${idx}`;
		clearTimeout(frm[key]);
		frm[key] = setTimeout(run, delay);
	});
}

function _apply_llm_grid_state(frm) {
	if (!frm) return;
	if (frm._pilot_llm_row_states) {
		_repaint_llm_provider_rows(frm);
		return;
	}
	_refresh_llm_provider_ui(frm, { silent: true });
}

function _set_limited_cell(grid_row, text) {
	if (!grid_row || !grid_row.doc) return;
	grid_row.doc.limited = text || "";
	if (grid_row.columns && grid_row.columns.limited) {
		grid_row.columns.limited.static_area.html(frappe.utils.escape_html(text || ""));
	}
	try {
		grid_row.refresh_field("limited");
	} catch (e) {
		// column not mounted yet
	}
}

function _apply_llm_grid_row(frm, grid_row, rowStates) {
	if (!grid_row || !grid_row.doc) return;
	const states = rowStates || frm._pilot_llm_row_states || {};
	const state = _find_row_state(grid_row.doc, states);
	_set_limited_cell(grid_row, _format_limited_field(state));
	_paint_llm_provider_row(grid_row, states);
}

function _sync_llm_limited_fields(frm, rowStates) {
	const states = rowStates || {};
	const grid = frm.get_field("llm_providers");
	if (!grid || !grid.grid) return;

	(frm.doc.llm_providers || []).forEach((row) => {
		const state = _find_row_state(row, states);
		const text = _format_limited_field(state);
		row.limited = text;
		const grid_row = grid.grid.grid_rows_by_docname[row.name];
		if (grid_row) {
			_set_limited_cell(grid_row, text);
		}
	});
}

function _clear_llm_row_paint(grid_row) {
	if (!grid_row || !grid_row.wrapper) return;
	const $wrapper = $(grid_row.wrapper);
	const $targets = grid_row.row ? $wrapper.add($(grid_row.row)) : $wrapper;
	$targets.removeClass("pilot-llm-row-active pilot-llm-row-limited pilot-llm-row-disabled");
	$wrapper.removeAttr("title");
}

function _apply_row_state_to_element($row, state, enabled) {
	if (!$row || !$row.length) return;
	$row.removeClass("pilot-llm-row-active pilot-llm-row-limited pilot-llm-row-disabled");
	if (!enabled) {
		$row.addClass("pilot-llm-row-disabled");
		return;
	}
	if (!state) return;
	if (state.status === "active") {
		$row.addClass("pilot-llm-row-active");
		$row.attr("title", __("Last used for a Pilot reply"));
	} else if (state.status === "rate_limited") {
		$row.addClass("pilot-llm-row-limited");
		let tip = __("Rate limited — skipped in failover");
		if (state.retry_in_sec) {
			tip += " — " + __("retry in ~{0}", [_format_retry_sec(state.retry_in_sec)]);
		}
		$row.attr("title", tip);
	}
}

function _paint_llm_provider_row(grid_row, rowStates) {
	if (!grid_row || !grid_row.wrapper) return;
	const states = rowStates || {};
	const state = _find_row_state(grid_row.doc, states);
	const $wrapper = $(grid_row.wrapper);
	const enabled = cint(grid_row.doc.enabled) !== 0;

	_clear_llm_row_paint(grid_row);
	_apply_row_state_to_element($wrapper, state, enabled);
	if (grid_row.row) {
		_apply_row_state_to_element($(grid_row.row), state, enabled);
	}
}

function _repaint_llm_provider_rows(frm) {
	const grid = frm.get_field("llm_providers");
	if (!grid || !grid.grid) return;
	const states = frm._pilot_llm_row_states || {};
	_sync_llm_limited_fields(frm, states);
	const seen = new Set();
	(grid.grid.grid_rows || []).forEach((grid_row) => {
		if (!grid_row || !grid_row.doc) return;
		seen.add(grid_row.doc.name);
		_paint_llm_provider_row(grid_row, states);
	});
	Object.values(grid.grid.grid_rows_by_docname || {}).forEach((grid_row) => {
		if (!grid_row || !grid_row.doc || seen.has(grid_row.doc.name)) return;
		_apply_llm_grid_row(frm, grid_row, states);
	});

	// DOM fallback — ensures colors apply even if grid_row objects are stale
	const $wrapper = grid.grid.wrapper;
	(frm.doc.llm_providers || []).forEach((row) => {
		if (!row || !row.name) return;
		const state = states[row.name] || _find_row_state(row, states);
		const $domRow = $wrapper.find(`.grid-row[data-name="${row.name}"]`);
		if ($domRow.length) {
			_apply_row_state_to_element($domRow, state, cint(row.enabled) !== 0);
		}
	});
}

function cint(val) {
	const n = parseInt(val, 10);
	return Number.isNaN(n) ? 0 : n;
}

function _bind_llm_model_sync(frm) {
	if (frm._pilot_llm_model_bound) return;
	frm._pilot_llm_model_bound = true;
	frappe.model.on("Pilot LLM Provider", "*", function (fieldname, value, doc) {
		if (fieldname === "limited" || !doc || doc.parentfield !== "llm_providers") return;
		if (!cur_frm || cur_frm.docname !== frm.docname) return;
		_schedule_llm_grid_sync(cur_frm);
	});
}

function _setup_llm_providers_grid(frm) {
	const grid = frm.get_field("llm_providers");
	if (!grid || !grid.grid) return;

	grid.grid.wrapper.addClass("pilot-llm-providers-grid");
	_bind_llm_model_sync(frm);

	const providerField = grid.grid.get_field("llm_provider");
	if (providerField) {
		providerField.get_query = () => ({
			filters: { is_active: 1 },
		});
	}

	$(frm.wrapper)
		.off("grid-row-render.pilot-llm")
		.on("grid-row-render.pilot-llm", (e, grid_row) => {
			if (!grid_row || !grid_row.grid || grid_row.grid.df.fieldname !== "llm_providers") {
				return;
			}
			if (frm._pilot_llm_row_states) {
				_apply_llm_grid_row(frm, grid_row, frm._pilot_llm_row_states);
			}
			_schedule_llm_grid_sync(frm);
		});

	grid.grid.wrapper
		.off("change.pilot-llm")
		.on("change.pilot-llm", () => {
			_schedule_llm_grid_sync(frm);
		});

	_schedule_llm_grid_sync(frm);
}

function _setup_llm_status_poll(frm) {
	if (frm._pilot_llm_poll_timer) {
		clearInterval(frm._pilot_llm_poll_timer);
	}
	frm._pilot_llm_poll_timer = setInterval(() => {
		if (frm.is_dirty()) return;
		_refresh_llm_provider_ui(frm, { silent: true });
	}, 60000);
}

function _refresh_llm_provider_ui(frm, opts) {
	opts = opts || {};
	const field = frm.get_field("api_key_status");
	if (!field && !opts.silent) return;

	frappe.call({
		method: "frappe_pilot.api.config.get_pilot_config",
		callback(r) {
			if (!r.message) return;
			const cfg = r.message;
			const status = cfg.llm_runtime_status || {};
			frm._pilot_llm_row_states = status.row_states || {};
			const grid = frm.get_field("llm_providers");
			if (grid && grid.grid) {
				grid.grid._pilot_llm_row_states = frm._pilot_llm_row_states;
			}
			if (!opts.silent && field) {
				_render_api_status_html(field, cfg, status);
			}
			_repaint_llm_provider_rows(frm);
			_schedule_llm_grid_sync(frm);
		},
	});
}

function _render_languages_help(frm) {
	const field = frm.get_field("languages_help_html");
	if (!field) return;
	field.$wrapper.html(
		'<p class="text-muted small">' +
		'<strong>English</strong> is the first row and cannot be removed or disabled. Add more rows linked to the <strong>Language</strong> list ' +
		'(e.g. <strong>Kurdish Sorani</strong> or <strong>Arabic</strong> / العربية). Use the <strong>Enabled</strong> checkbox per row: ' +
		'only checked languages appear in the sidebar locale toggle and get localized suggestion chips (when Pilot has translations). ' +
		'<strong>Suggestion Chip Languages</strong> controls whether chips show for all enabled locales, only the active sidebar locale, or active locale + English. ' +
		'Kurdish Sorani and Arabic include full UI + split chips; other languages use English sidebar chrome with LLM replies in that language.</p>'
	);
}

function _isEnglishPilotRow(row) {
	return row && row.language === PILOT_ENGLISH_LANGUAGE;
}

function _ensure_english_language_row(frm) {
	const rows = frm.doc.enabled_languages || [];
	const en_rows = rows.filter((row) => _isEnglishPilotRow(row));
	const other_rows = rows.filter((row) => !_isEnglishPilotRow(row));

	if (en_rows.length === 1 && rows[0] && _isEnglishPilotRow(rows[0]) && en_rows[0].enabled) {
		return;
	}

	frm.clear_table("enabled_languages");
	frm.add_child("enabled_languages", { language: PILOT_ENGLISH_LANGUAGE, enabled: 1 });
	other_rows.forEach((row) => {
		if (!row.language) return;
		frm.add_child("enabled_languages", {
			language: row.language,
			enabled: row.enabled,
		});
	});
	frm.refresh_field("enabled_languages");
}

function _lock_english_language_row(grid_row) {
	if (!_isEnglishPilotRow(grid_row.doc)) return;
	grid_row.toggle_editable("language", false);
	grid_row.toggle_editable("enabled", false);
	grid_row.wrapper.find(".grid-delete-row").hide();
}

function _setup_enabled_languages_grid(frm) {
	const grid = frm.get_field("enabled_languages");
	if (!grid || !grid.grid) return;

	if (!grid._pilot_english_grid_hooks) {
		grid._pilot_english_grid_hooks = true;
		grid.grid.wrapper.on("grid-row-render", (e) => {
			_lock_english_language_row(e.detail);
		});
	}

	grid.grid.grid_rows.forEach((grid_row) => _lock_english_language_row(grid_row));

	grid.grid.get_field("language").get_query = function (doc) {
		if (_isEnglishPilotRow(doc)) {
			return { filters: { name: PILOT_ENGLISH_LANGUAGE } };
		}
		return {
			filters: {
				language_code: ["!=", "en"],
				enabled: 1,
			},
		};
	};
}

function _normalize_llm_priorities(frm) {
	const rows = (frm.doc.llm_providers || []).filter((r) => r.enabled);
	if (!rows.length) {
		_schedule_llm_grid_sync(frm);
		return;
	}
	rows.sort((a, b) => (a.priority || 0) - (b.priority || 0));
	let next = 1;
	const updates = [];
	rows.forEach((row) => {
		if (row.priority !== next) {
			updates.push(frappe.model.set_value(row.doctype, row.name, "priority", next));
		}
		next += 1;
	});
	if (updates.length) {
		Promise.all(updates).then(() => _schedule_llm_grid_sync(frm));
	} else {
		_schedule_llm_grid_sync(frm);
	}
}

function _render_navigation_help(frm) {
	const field = frm.get_field("section_break_navigation");
	if (!field || !field.$wrapper) return;
	const autoNav = frm.doc.auto_navigate ? "on" : "off";
	const closeSide = frm.doc.close_sidebar_on_navigate ? "on" : "off";
	field.$wrapper.find(".frai-nav-help").remove();
	field.$wrapper.append(
		'<p class="text-muted small frai-nav-help">' +
		`Auto-navigate: <strong>${autoNav}</strong>. Close sidebar after navigation: <strong>${closeSide}</strong>.` +
		"</p>"
	);
}

function _show_llm_test_results(data) {
	if (!data) {
		frappe.msgprint({
			title: __("Connection Test"),
			indicator: "red",
			message: __("Unknown error"),
		});
		return;
	}

	const results = data.results || [];
	if (!results.length) {
		frappe.msgprint({
			title: __("Connection Test"),
			indicator: "red",
			message: frappe.utils.escape_html(data.message || __("No enabled LLM provider rows configured.")),
		});
		return;
	}

	const rowsHtml = results
		.map((row) => {
			const status = row.ok ? __("OK") : __("Failed");
			const pillClass = row.ok ? "green" : "red";
			const detail = row.ok
				? `<span class="text-muted">${frappe.utils.escape_html(row.model || "")}</span>`
				: `<span class="text-danger small">${frappe.utils.escape_html(row.error || "")}</span>`;
			return (
				`<div class="pilot-llm-test-row" style="display:flex;align-items:flex-start;gap:10px;padding:8px 0;border-bottom:1px solid var(--border-color,#d1d8dd)">` +
				`<span class="indicator-pill ${pillClass} filterable no-indicator-dot" style="flex-shrink:0;margin-top:2px">${status}</span>` +
				`<div style="min-width:0">` +
				`<div><strong>${frappe.utils.escape_html(row.label)}</strong>` +
				` <span class="text-muted">(${frappe.utils.escape_html(row.provider || row.llm_provider || "")} · P${row.priority})</span></div>` +
				`<div style="margin-top:2px">${detail}</div>` +
				`</div></div>`
			);
		})
		.join("");

	const allOk = data.all_ok === true;
	const anyOk = data.ok === true;
	frappe.msgprint({
		title: allOk ? __("Connection Test — All OK") : anyOk ? __("Connection Test — Partial") : __("Connection Test — Failed"),
		indicator: allOk ? "green" : anyOk ? "orange" : "red",
		message: `<div class="pilot-llm-test-results">${rowsHtml}</div>`,
	});
}

function _render_api_status(frm) {
	_refresh_llm_provider_ui(frm);
}

function _render_api_status_html(field, cfg, status) {
	const hasKey = cfg.has_api_key;
	const lastSuccess = status.last_success_row || {};
	const current = status.current_row || {};
	const primary = status.primary_row || {};
	const mode = status.llm_failover_mode || cfg.llm_failover_mode || "Both";
	const rowCount = status.enabled_row_count || (cfg.llm_provider_options || []).length;
	const rateLimited = status.rate_limited_rows || [];
	const isFailover = status.is_failover_active;

	let badgeHtml;
	if (!hasKey) {
		badgeHtml = `<span class="indicator-pill red filterable no-indicator-dot">${__("Not configured")}</span>`;
	} else if (lastSuccess.name) {
		badgeHtml =
			`<div style="margin-bottom:6px">` +
			`<span class="indicator-pill green filterable no-indicator-dot">${__("Last used")}</span> ` +
			`<strong>${frappe.utils.escape_html(lastSuccess.row_label)}</strong>` +
			` <span class="text-muted">(${frappe.utils.escape_html(lastSuccess.provider)} · P${lastSuccess.priority})</span>` +
			`</div>`;
	} else if (current.name) {
		const pillClass = isFailover ? "orange" : "green";
		badgeHtml =
			`<div style="margin-bottom:6px">` +
			`<span class="indicator-pill ${pillClass} filterable no-indicator-dot">${__("Active LLM")}</span> ` +
			`<strong>${frappe.utils.escape_html(current.row_label)}</strong>` +
			` <span class="text-muted">(${frappe.utils.escape_html(current.provider)} · P${current.priority})</span>` +
			`</div>`;
	} else {
		badgeHtml = `<span class="indicator-pill green filterable no-indicator-dot">${__("Configured")}</span>`;
	}

	let detailLines = [];
	if (primary.name && lastSuccess.name && primary.name !== lastSuccess.name) {
		detailLines.push(
			`${__("Primary")}: <strong>${frappe.utils.escape_html(primary.row_label)}</strong>` +
			` (${frappe.utils.escape_html(primary.provider)} · P${primary.priority})`
		);
	}
	if (rateLimited.length) {
		const limited = rateLimited
			.map((row) => `P${row.priority} ${frappe.utils.escape_html(row.row_label)}`)
			.join(", ");
		detailLines.push(`${__("Rate limited")}: ${limited}`);
	}
	if (status.is_session_pinned) {
		detailLines.push(__("Session row pinned in sidebar"));
	}

	const detailHtml = detailLines.length
		? `<ul class="text-muted small" style="margin:6px 0 0 18px;padding:0">${detailLines
				.map((line) => `<li style="margin-bottom:2px">${line}</li>`)
				.join("")}</ul>`
		: "";

		const legendHtml =
		`<p class="text-muted small pilot-llm-grid-legend" style="margin-top:8px">` +
		`<span class="indicator-pill green no-indicator-dot" style="font-size:10px;padding:2px 8px">${__("Green")}</span> ${__("last used for a reply")} &nbsp; ` +
		`<span class="indicator-pill red no-indicator-dot" style="font-size:10px;padding:2px 8px">${__("Red")}</span> ${__("rate limited")} &nbsp; ` +
		`${__("no color")} = ${__("standby")}.<br>` +
		`${__("Limited column shows cooldown when rate limited.")}` +
		`</p>`;
	
	field.$wrapper.html(
		badgeHtml +
		`<p class="text-muted small" style="margin-top:6px">` +
		`${__("Failover")}: <strong>${frappe.utils.escape_html(mode)}</strong>. ` +
		`${rowCount} ${__("enabled row(s)")}. ${__("Lower priority is tried first.")}` +
		`</p>` +
		detailHtml +
		legendHtml
	);
}
