const PILOT_ENGLISH_LANGUAGE = "en";

frappe.ui.form.on("Pilot Settings", {
	refresh(frm) {
		_render_languages_help(frm);
		_render_navigation_help(frm);
		_render_api_status(frm);
		_ensure_english_language_row(frm);
		_setup_enabled_languages_grid(frm);
		frm.add_custom_button(__("Test Connection"), () => {
			frappe.call({
				method: "frappe_pilot.api.config.test_api_connection",
				freeze: true,
				freeze_message: __("Testing API connection…"),
				callback(r) {
					if (r.message && r.message.ok) {
						frappe.show_alert({
							message: r.message.message,
							indicator: "green",
						});
					} else {
						frappe.msgprint({
							title: __("Connection Failed"),
							indicator: "red",
							message: (r.message && r.message.message) || __("Unknown error"),
						});
					}
					_render_api_status(frm);
				},
			});
		});
	},
	llm_provider() {
		_render_api_status(cur_frm);
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
	},
	before_enabled_languages_remove(frm, cdt, cdn) {
		const row = locals[cdt][cdn];
		if (row && row.language === PILOT_ENGLISH_LANGUAGE) {
			frappe.throw(__("English is required in Pilot and cannot be removed."));
		}
	},
});

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

function _render_api_status(frm) {
	const field = frm.get_field("api_key_status");
	if (!field) return;

	frappe.call({
		method: "frappe_pilot.api.config.get_pilot_config",
		callback(r) {
			if (!r.message) return;
			const hasKey = r.message.has_api_key;
			const provider = r.message.active_provider || "Groq";
			const badge = hasKey
				? `<span class="indicator-pill green filterable no-indicator-dot">Configured (${provider})</span>`
				: `<span class="indicator-pill red filterable no-indicator-dot">Not configured</span>`;
			field.$wrapper.html(
				`<div style="margin-bottom:8px">${badge}</div>` +
				`<p class="text-muted small">Save API keys below. site_config.json values are used when password fields are empty.</p>`
			);
		},
	});
}
