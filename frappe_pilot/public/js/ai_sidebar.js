// ============================================================
// ai_sidebar.js — Frappe Pilot (v2 split-chips)
// ============================================================

var FRAI_BUILD = "2026-06-07-trigger-hover";

var PLACEHOLDER_FALLBACKS = {
    placeholder_advisor:        "Ask about this page or where to go…",
    placeholder_build:          "Describe a field, DocType, or automation…",
    placeholder_advisor_form:   "Summarize or ask about {label}…",
    placeholder_advisor_form_new: "What should I enter on this {doctype}?…",
    placeholder_advisor_list:   "Ask about this {doctype} list…",
    placeholder_advisor_report: "Explain or question this {report} report…",
    placeholder_advisor_page:   "Ask about this page or where to go…",
    placeholder_build_form:     "Add a field, script, or workflow for {doctype}…",
    placeholder_build_list:     "Build something for {doctype}…",
    placeholder_build_page:     "Describe a field, DocType, or automation…",
};

var PANEL_WIDTH_MIN  = 280;
var PANEL_WIDTH_MAX  = 640;
var PANEL_HEIGHT_MIN = 240;
var PANEL_HEIGHT_MAX_VH = 0.75;

var FRAI = {
    isOpen:              false,
    activeTab:           "advisor",
    activeBuildSubtab:   "chat",
    doctype:             null,
    docname:             null,
    isNew:               false,
    route:               "",
    listDoctype:         null,
    lastContextKey:      "",
    sending:             false,
    panelWidth:          360,
    panelHeight:         null,
    sidebarPosition:     "right",
    isResizing:          false,
    pendingSessionKey:   null,
    codingHistory:       [],
    analyzeMode:         "explain",
    replyLocale:         "en",
    sidebarLocale:       "en",
    config:              null,
    apiSetupActive:      false,
    _savedSubtitle:      "",
    suggestionsCache:    {},
    chipMeta:            {},
    pendingSuggestions:  {},
};

var ANALYZE_DIAGNOSE_CHIPS = {
    "Diagnose this record":       true,
    "Flag anything unusual":      true,
    "Why are these records here?": true,
    "Why is this total high?":    true,
};

var TOOL_LABELS = {
    "create_custom_field":  "CUSTOM FIELD",
    "create_server_script": "SERVER SCRIPT",
    "create_client_script": "CLIENT SCRIPT",
    "create_workflow":      "WORKFLOW",
    "create_doctype":       "DOCTYPE",
    "create_documents":     "RECORDS",
};

var POST_APPLY_SUGGESTIONS = {
    "create_custom_field":  "Want me to add a validation script for this field?",
    "create_server_script": "Want me to add a matching client-side trigger?",
    "create_client_script": "Want me to add server-side validation too?",
    "create_workflow":      "Want me to set up email alerts for each state change?",
    "create_doctype":       "Want me to seed it with some sample records?",
    "create_documents":     "Want me to create a list report for these records?",
};

var CODING_TYPING_LABELS  = ["Thinking…", "Reading schema…", "Preparing change…", "Validating…"];
var GUIDE_TYPING_LABELS   = ["Thinking…", "Searching docs…", "Preparing answer…"];
var ADVISOR_TYPING_LABELS = ["Analyzing…", "Reading document…", "Preparing summary…"];

function _loadSidebarLocale() {
    try {
        var saved = localStorage.getItem("frai_sidebar_locale");
        if (saved) return saved;
    } catch (e) { /* ignore */ }
    return "en";
}

function _saveSidebarLocale(loc) {
    try { localStorage.setItem("frai_sidebar_locale", loc); } catch (e) { /* ignore */ }
}

function _loadPanelWidth() {
    try {
        var w = parseInt(localStorage.getItem("frai_panel_width"), 10);
        if (w >= PANEL_WIDTH_MIN && w <= PANEL_WIDTH_MAX) return w;
    } catch (e) { /* ignore */ }
    return 360;
}

function _savePanelWidth(w) {
    try { localStorage.setItem("frai_panel_width", String(w)); } catch (e) { /* ignore */ }
}

function _defaultPanelHeight() {
    return Math.round(window.innerHeight * 0.45);
}

function _loadPanelHeight() {
    try {
        var h = parseInt(localStorage.getItem("frai_panel_height"), 10);
        var maxH = Math.round(window.innerHeight * PANEL_HEIGHT_MAX_VH);
        if (h >= PANEL_HEIGHT_MIN && h <= maxH) return h;
    } catch (e) { /* ignore */ }
    return _defaultPanelHeight();
}

function _savePanelHeight(h) {
    try { localStorage.setItem("frai_panel_height", String(h)); } catch (e) { /* ignore */ }
}

function _loadSidebarPositionOverride() {
    try {
        var p = localStorage.getItem("frai_sidebar_position");
        if (p === "right" || p === "left" || p === "bottom") return p;
    } catch (e) { /* ignore */ }
    return null;
}

function _saveSidebarPositionOverride(pos) {
    try { localStorage.setItem("frai_sidebar_position", pos); } catch (e) { /* ignore */ }
}

function _clearSidebarPositionOverride() {
    try { localStorage.removeItem("frai_sidebar_position"); } catch (e) { /* ignore */ }
}

function _resolveSidebarPosition() {
    var user = _loadSidebarPositionOverride();
    if (user) return user;
    var site = (FRAI.config && FRAI.config.sidebar_position) || "right";
    if (site === "left" || site === "bottom") return site;
    return "right";
}

function _hasPositionOverride() {
    return !!_loadSidebarPositionOverride();
}

var HISTORY_BADGE_MAP = {
    "DocType":       { cls: "frai-hb-doctype",   label: "DocType"  },
    "Custom Field":  { cls: "frai-hb-field",      label: "Field"    },
    "Server Script": { cls: "frai-hb-script",     label: "Script"   },
    "Client Script": { cls: "frai-hb-script",     label: "Script"   },
    "Workflow":      { cls: "frai-hb-workflow",   label: "Workflow" },
    "Documents":     { cls: "frai-hb-documents",  label: "Records"  },
};

var _typingLabelTimers = {};

$(document).ready(function () {
    _bootstrapPilot();
});

function _bootstrapPilot() {
    frappe.call({
        method: "frappe_pilot.api.config.get_pilot_config",
        callback: function (r) {
            if (!r || !r.message) return;
            FRAI.config = r.message;
            if (!FRAI.config.enabled) return;

            FRAI.sidebarLocale = _loadSidebarLocale();
            _normalizeSidebarLocale();

            FRAI.panelWidth = _loadPanelWidth();
            FRAI.panelHeight = _loadPanelHeight();
            FRAI.sidebarPosition = _resolveSidebarPosition();

            _injectCSS();
            _buildDOM();
            _bindEvents();
            _bindResizeEvents();
            _applySidebarPosition(FRAI.sidebarPosition);
            _renderLocaleToggle();
            _applyTabVisibility();
            _applyPilotLocale();
            _syncTriggerState();
            _scheduleContextCheck();
            console.info("[Frappe Pilot] sidebar build:", FRAI_BUILD);

            if (FRAI.config.is_system_manager) {
                var gear = document.getElementById("frai-settings-gear");
                if (gear) gear.style.display = "flex";
            }

            window.FrappePilot = window.FrappePilot || {};
            window.FrappePilot.refreshConfig = _refreshPilotConfig;
        },
        error: function () {
            console.warn("[Frappe Pilot] Could not load pilot config.");
        },
    });
}


// ════════════════════════════════════════════════════════════════
// CSS
// ════════════════════════════════════════════════════════════════
function _injectCSS() {
    var style = document.createElement("style");
    style.id = "frai-styles";
    style.textContent = `

/* ── Trigger (edge rail) ── */
#frai-trigger {
    --frai-trigger-edge: 0px;
    --frai-trigger-accent: var(--primary, #2490ef);
    position: fixed;
    z-index: 1050;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0;
    padding: 0;
    border: none;
    background: transparent;
    cursor: pointer;
    user-select: none;
    font: inherit;
    color: inherit;
    outline: none;
    -webkit-tap-highlight-color: transparent;
    transition:
        --frai-trigger-edge .24s cubic-bezier(.4,0,.2,1),
        transform .24s cubic-bezier(.4,0,.2,1);
}
#frai-trigger.frai-resizing {
    transition: none !important;
}
#frai-trigger:focus-visible .frai-trigger-rail {
    box-shadow:
        0 0 0 2px var(--fg-color, #fff),
        0 0 0 4px var(--frai-trigger-accent);
}
#frai-trigger.frai-pos-right {
    right: var(--frai-trigger-edge);
    top: 50%;
    transform: translateY(-50%);
}
#frai-trigger.frai-pos-left {
    left: var(--frai-trigger-edge);
    top: 50%;
    transform: translateY(-50%);
}
#frai-trigger.frai-pos-bottom {
    bottom: var(--frai-trigger-edge);
    left: 50%;
    transform: translateX(-50%);
}
.frai-trigger-rail {
    position: relative;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    overflow: hidden;
    background:
        linear-gradient(135deg, rgba(36,144,239,.08) 0%, rgba(36,144,239,.02) 55%, transparent 100%),
        color-mix(in srgb, var(--fg-color, #fff) 92%, var(--frai-trigger-accent) 8%);
    border: 1px solid color-mix(in srgb, var(--border-color, #d1d8dd) 80%, var(--frai-trigger-accent) 20%);
    box-shadow:
        0 8px 24px rgba(15, 23, 42, .08),
        0 1px 0 rgba(255,255,255,.55) inset;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    transition:
        padding .22s cubic-bezier(.34,1.2,.64,1),
        gap .22s cubic-bezier(.34,1.2,.64,1),
        transform .22s cubic-bezier(.34,1.2,.64,1),
        box-shadow .2s ease,
        border-color .2s ease,
        background .2s ease;
}
.frai-trigger-beam {
    position: absolute;
    pointer-events: none;
    background: linear-gradient(
        180deg,
        transparent 0%,
        var(--frai-trigger-accent) 42%,
        color-mix(in srgb, var(--frai-trigger-accent) 55%, #7dd3fc) 58%,
        transparent 100%
    );
    opacity: .85;
    transition: opacity .2s ease;
}
#frai-trigger.frai-pos-right .frai-trigger-rail {
    flex-direction: column;
    padding: 14px 9px 12px 11px;
    border-right: none;
    border-radius: 14px 0 0 14px;
    transform-origin: right center;
}
#frai-trigger.frai-pos-right .frai-trigger-beam {
    top: 10%;
    right: 0;
    width: 3px;
    height: 80%;
    border-radius: 3px 0 0 3px;
}
#frai-trigger.frai-pos-left .frai-trigger-rail {
    flex-direction: column;
    padding: 14px 11px 12px 9px;
    border-left: none;
    border-radius: 0 14px 14px 0;
    transform-origin: left center;
}
#frai-trigger.frai-pos-left .frai-trigger-beam {
    top: 10%;
    left: 0;
    width: 3px;
    height: 80%;
    border-radius: 0 3px 3px 0;
}
#frai-trigger.frai-pos-bottom .frai-trigger-rail {
    flex-direction: row;
    padding: 9px 16px 11px;
    border-bottom: none;
    border-radius: 14px 14px 0 0;
    transform-origin: center bottom;
}
#frai-trigger.frai-pos-bottom .frai-trigger-beam {
    left: 12%;
    bottom: 0;
    width: 76%;
    height: 3px;
    border-radius: 3px 3px 0 0;
    background: linear-gradient(
        90deg,
        transparent 0%,
        var(--frai-trigger-accent) 42%,
        color-mix(in srgb, var(--frai-trigger-accent) 55%, #7dd3fc) 58%,
        transparent 100%
    );
}
#frai-trigger:hover .frai-trigger-rail,
#frai-trigger:focus-visible .frai-trigger-rail {
    box-shadow:
        0 12px 28px rgba(36, 144, 239, .16),
        0 1px 0 rgba(255,255,255,.6) inset;
    border-color: color-mix(in srgb, var(--frai-trigger-accent) 35%, var(--border-color, #d1d8dd));
    gap: 10px;
}
#frai-trigger.frai-pos-right:hover .frai-trigger-rail,
#frai-trigger.frai-pos-right:focus-visible .frai-trigger-rail {
    padding: 15px 9px 13px 16px;
    transform: scale(1.04);
}
#frai-trigger.frai-pos-left:hover .frai-trigger-rail,
#frai-trigger.frai-pos-left:focus-visible .frai-trigger-rail {
    padding: 15px 16px 13px 9px;
    transform: scale(1.04);
}
#frai-trigger.frai-pos-bottom:hover .frai-trigger-rail,
#frai-trigger.frai-pos-bottom:focus-visible .frai-trigger-rail {
    padding: 12px 18px 11px;
    transform: scale(1.04);
}
#frai-trigger.frai-trigger-open.frai-pos-right:hover .frai-trigger-rail,
#frai-trigger.frai-trigger-open.frai-pos-right:focus-visible .frai-trigger-rail {
    padding: 12px 7px;
}
#frai-trigger.frai-trigger-open.frai-pos-left:hover .frai-trigger-rail,
#frai-trigger.frai-trigger-open.frai-pos-left:focus-visible .frai-trigger-rail {
    padding: 12px 7px;
}
#frai-trigger.frai-trigger-open.frai-pos-bottom:hover .frai-trigger-rail,
#frai-trigger.frai-trigger-open.frai-pos-bottom:focus-visible .frai-trigger-rail {
    padding: 8px 14px;
}
#frai-trigger:active .frai-trigger-rail {
    transform: scale(.98);
}
.frai-trigger-icon {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 9px;
    background: color-mix(in srgb, var(--frai-trigger-accent) 14%, var(--fg-color, #fff));
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--frai-trigger-accent) 22%, transparent);
    flex-shrink: 0;
    transition: transform .25s cubic-bezier(.34,1.56,.64,1), box-shadow .2s ease;
}
.frai-trigger-icon svg {
    width: 15px;
    height: 15px;
    stroke: var(--frai-trigger-accent);
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}
#frai-trigger:hover .frai-trigger-icon {
    transform: scale(1.06) rotate(-4deg);
    box-shadow:
        0 0 0 1px color-mix(in srgb, var(--frai-trigger-accent) 30%, transparent),
        0 4px 14px color-mix(in srgb, var(--frai-trigger-accent) 28%, transparent);
}
.frai-trigger-copy {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    min-width: 0;
}
#frai-trigger-label {
    font-size: 10px;
    font-weight: 700;
    letter-spacing: .14em;
    text-transform: uppercase;
    color: var(--text-color, #36414c);
    white-space: nowrap;
    line-height: 1;
    transition:
        transform .22s cubic-bezier(.34,1.2,.64,1),
        letter-spacing .22s cubic-bezier(.34,1.2,.64,1),
        color .2s ease;
}
#frai-trigger.frai-pos-right .frai-trigger-copy,
#frai-trigger.frai-pos-left .frai-trigger-copy {
    writing-mode: vertical-rl;
    text-orientation: mixed;
    transition: transform .22s cubic-bezier(.34,1.2,.64,1);
}
#frai-trigger.frai-pos-right #frai-trigger-label {
    transform: rotate(180deg);
}
#frai-trigger:not(.frai-trigger-open):hover #frai-trigger-label,
#frai-trigger:not(.frai-trigger-open):focus-visible #frai-trigger-label {
    letter-spacing: .2em;
    color: var(--frai-trigger-accent);
}
#frai-trigger.frai-pos-right:not(.frai-trigger-open):hover #frai-trigger-label,
#frai-trigger.frai-pos-right:not(.frai-trigger-open):focus-visible #frai-trigger-label {
    transform: rotate(180deg) scale(1.08);
}
#frai-trigger.frai-pos-left:not(.frai-trigger-open):hover #frai-trigger-label,
#frai-trigger.frai-pos-left:not(.frai-trigger-open):focus-visible #frai-trigger-label {
    transform: scale(1.08);
}
#frai-trigger.frai-pos-bottom:not(.frai-trigger-open):hover #frai-trigger-label,
#frai-trigger.frai-pos-bottom:not(.frai-trigger-open):focus-visible #frai-trigger-label {
    transform: scale(1.06);
}
#frai-trigger.frai-trigger-open .frai-trigger-copy {
    display: none;
}
#frai-trigger.frai-trigger-open .frai-trigger-rail {
    padding: 10px 8px;
    background: var(--fg-color, #fff);
}
#frai-trigger.frai-trigger-open.frai-pos-right .frai-trigger-rail,
#frai-trigger.frai-trigger-open.frai-pos-left .frai-trigger-rail {
    padding: 12px 7px;
}
#frai-trigger.frai-trigger-open.frai-pos-bottom .frai-trigger-rail {
    padding: 7px 12px;
}
#frai-trigger.frai-trigger-open .frai-trigger-beam {
    opacity: 1;
}
#frai-trigger.frai-trigger-pulse:not(.frai-trigger-open) .frai-trigger-icon {
    animation: frai-trigger-glow 2.8s ease-in-out infinite;
}
@keyframes frai-trigger-glow {
    0%, 100% {
        box-shadow:
            0 0 0 1px color-mix(in srgb, var(--frai-trigger-accent) 22%, transparent),
            0 0 0 0 color-mix(in srgb, var(--frai-trigger-accent) 0%, transparent);
    }
    50% {
        box-shadow:
            0 0 0 1px color-mix(in srgb, var(--frai-trigger-accent) 35%, transparent),
            0 0 0 6px color-mix(in srgb, var(--frai-trigger-accent) 14%, transparent);
    }
}
@media (prefers-reduced-motion: reduce) {
    #frai-trigger.frai-trigger-pulse:not(.frai-trigger-open) .frai-trigger-icon {
        animation: none;
    }
    #frai-trigger,
    #frai-trigger .frai-trigger-rail,
    #frai-trigger .frai-trigger-icon,
    #frai-trigger #frai-trigger-label,
    #frai-trigger .frai-trigger-copy {
        transition: none;
    }
}

/* ── Resize handle ── */
#frai-resize-handle {
    position: absolute;
    z-index: 10;
    background: transparent;
    transition: background .15s;
}
#frai-panel.frai-pos-right #frai-resize-handle,
#frai-panel.frai-pos-left #frai-resize-handle {
    top: 0;
    width: 5px;
    height: 100%;
    cursor: ew-resize;
}
#frai-panel.frai-pos-right #frai-resize-handle { left: 0; }
#frai-panel.frai-pos-left #frai-resize-handle { right: 0; left: auto; }
#frai-panel.frai-pos-bottom #frai-resize-handle {
    top: 0;
    left: 0;
    width: 100%;
    height: 5px;
    cursor: ns-resize;
}
#frai-resize-handle:hover,
#frai-resize-handle.frai-dragging {
    background: var(--primary, #2490ef);
    opacity: .25;
}

/* ── Panel ── */
#frai-panel {
    position: fixed;
    z-index: 1049;
    display: flex;
    flex-direction: column;
    background: var(--fg-color, #fff);
    overflow: hidden;
    transition: transform .22s cubic-bezier(.4,0,.2,1);
}
#frai-panel.frai-resizing { transition: none; }
#frai-panel.frai-pos-right {
    top: 0;
    right: 0;
    height: 100dvh;
    min-width: 280px;
    max-width: 640px;
    border-left: 1px solid var(--border-color, #d1d8dd);
    box-shadow: -4px 0 20px rgba(0,0,0,.07);
    transform: translateX(100%);
}
#frai-panel.frai-pos-right.frai-open { transform: translateX(0); }
#frai-panel.frai-pos-left {
    top: 0;
    left: 0;
    height: 100dvh;
    min-width: 280px;
    max-width: 640px;
    border-right: 1px solid var(--border-color, #d1d8dd);
    box-shadow: 4px 0 20px rgba(0,0,0,.07);
    transform: translateX(-100%);
}
#frai-panel.frai-pos-left.frai-open { transform: translateX(0); }
#frai-panel.frai-pos-bottom {
    bottom: 0;
    left: 0;
    right: 0;
    width: 100%;
    min-height: 240px;
    border-top: 1px solid var(--border-color, #d1d8dd);
    box-shadow: 0 -4px 24px rgba(0,0,0,.08);
    transform: translateY(100%);
}
#frai-panel.frai-pos-bottom.frai-open { transform: translateY(0); }

/* ── Header (light, Frappe-native) ── */
#frai-header {
    flex-shrink: 0;
    padding: 12px 14px 0;
    background: var(--fg-color, #fff);
    border-bottom: 1px solid var(--border-color, #d1d8dd);
}
#frai-header-actions {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    padding: 0 14px 6px;
}
#frai-header-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
#frai-header-controls {
    display: flex;
    align-items: center;
    gap: 4px;
    flex-shrink: 0;
}
#frai-position-toggle {
    display: flex;
    align-items: center;
    gap: 2px;
    background: var(--control-bg, #f4f5f6);
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 8px;
    padding: 2px;
}
.frai-position-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 26px;
    height: 24px;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted, #8d99a6);
    cursor: pointer;
    padding: 0;
    transition: color .13s, background .13s;
}
.frai-position-btn:hover { color: var(--text-color, #36414c); }
.frai-position-btn.frai-position-active {
    background: var(--fg-color, #fff);
    color: var(--primary, #2490ef);
    box-shadow: 0 1px 3px rgba(0,0,0,.08);
}
.frai-position-btn svg {
    width: 14px;
    height: 14px;
    stroke: currentColor;
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}
.frai-position-reset {
    font-size: 10px;
    color: var(--text-muted, #8d99a6);
    background: none;
    border: none;
    cursor: pointer;
    padding: 0 4px;
    margin-left: 2px;
    opacity: 0;
    pointer-events: none;
    transition: opacity .15s, color .13s;
}
.frai-position-reset.frai-visible {
    opacity: 1;
    pointer-events: auto;
}
.frai-position-reset:hover { color: var(--primary, #2490ef); }
#frai-icon-wrap {
    width: 28px; height: 28px;
    border-radius: 6px;
    background: var(--primary-light, #e4f2ff);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
#frai-icon-wrap svg {
    width: 15px; height: 15px;
    stroke: var(--primary, #2490ef);
    fill: none;
    stroke-width: 2;
    stroke-linecap: round;
    stroke-linejoin: round;
}
#frai-title-wrap { flex: 1; min-width: 0; }
#frai-title {
    font-size: 13px;
    font-weight: 600;
    color: var(--text-color, #36414c);
    line-height: 1.2;
}
#frai-subtitle {
    font-size: 11px;
    color: var(--text-muted, #8d99a6);
    margin-top: 1px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
#frai-close {
    width: 26px; height: 26px;
    border-radius: 6px;
    border: none;
    background: transparent;
    color: var(--text-muted, #8d99a6);
    font-size: 15px;
    line-height: 1;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background .12s, color .12s;
}
#frai-close:hover {
    background: var(--control-bg, #f4f5f6);
    color: var(--text-color, #36414c);
}

/* ── Tabs (light background, Frappe-native) ── */
#frai-tabs {
    display: flex;
    margin: 0 -14px;
    padding: 0 14px;
}
.frai-tab {
    flex: 1;
    padding: 8px 0 9px;
    font-size: 12px;
    font-weight: 500;
    text-align: center;
    cursor: pointer;
    border: none;
    background: transparent;
    color: var(--text-muted, #8d99a6);
    border-bottom: 2px solid transparent;
    transition: color .13s, border-color .13s;
    margin-bottom: -1px;
}
.frai-tab:hover { color: var(--text-color, #36414c); }
.frai-tab.frai-tab-active {
    color: var(--primary, #2490ef);
    border-bottom-color: var(--primary, #2490ef);
    font-weight: 600;
}

/* ── Build sub-tabs ── */
#frai-subtabs {
    display: none;
    margin: 0 -14px;
    padding: 0 14px;
    background: var(--control-bg, #f4f5f6);
    border-bottom: 1px solid var(--border-color, #d1d8dd);
}
#frai-subtabs.frai-subtabs-visible { display: flex; }
.frai-subtab {
    flex: 1;
    padding: 6px 0 7px;
    font-size: 11px;
    font-weight: 500;
    text-align: center;
    cursor: pointer;
    border: none;
    background: transparent;
    color: var(--text-muted, #8d99a6);
    border-bottom: 2px solid transparent;
    transition: color .13s, border-color .13s;
}
.frai-subtab:hover { color: var(--text-color, #36414c); }
.frai-subtab.frai-subtab-active {
    color: var(--primary, #2490ef);
    border-bottom-color: var(--primary, #2490ef);
    font-weight: 600;
}

/* ── Body + panes ── */
#frai-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
.frai-tab-pane {
    flex: 1;
    display: none;
    flex-direction: column;
    overflow: hidden;
}
.frai-tab-pane.frai-pane-active { display: flex; }

/* ── Messages area ── */
.frai-messages-area {
    flex: 1;
    overflow-y: auto;
    padding: 14px 12px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    scroll-behavior: smooth;
}
.frai-messages-area::-webkit-scrollbar { width: 4px; }
.frai-messages-area::-webkit-scrollbar-track { background: transparent; }
.frai-messages-area::-webkit-scrollbar-thumb {
    background: var(--border-color, #d1d8dd);
    border-radius: 4px;
}

/* ── Bubbles ── */
.frai-bubble {
    max-width: 90%;
    padding: 9px 12px;
    border-radius: 4px 10px 10px 10px;
    font-size: 12.5px;
    line-height: 1.65;
    word-break: break-word;
    animation: frai-in .15s ease;
}
@keyframes frai-in {
    from { opacity:0; transform:translateY(4px); }
    to   { opacity:1; transform:translateY(0); }
}
.frai-bubble.frai-agent {
    align-self: flex-start;
    background: var(--control-bg, #f4f5f6);
    color: var(--text-color, #36414c);
    border: 1px solid var(--border-color, #d1d8dd);
}
.frai-bubble.frai-user {
    align-self: flex-end;
    background: var(--primary, #2490ef);
    color: #fff;
    border-radius: 10px 4px 10px 10px;
    border: none;
}
.frai-bubble.frai-error {
    align-self: flex-start;
    background: var(--red-highlight-color, #fff5f5);
    color: var(--red, #e74c3c);
    border: 1px solid #fbd5d5;
}
.frai-context-hint {
    align-self: flex-start;
    font-size: 10.5px;
    color: var(--text-muted, #8d99a6);
    font-style: italic;
    padding: 0 4px;
    margin-top: -4px;
}

/* ── Chips (advisor tab) ── */
.frai-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    margin-top: 8px;
}
.frai-chip {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px solid var(--border-color, #d1d8dd);
    background: var(--fg-color, #fff);
    color: var(--text-muted, #8d99a6);
    cursor: pointer;
    transition: border-color .12s, color .12s, background .12s;
    line-height: 1.4;
    text-align: left;
}
.frai-chip:hover {
    border-color: var(--primary, #2490ef);
    color: var(--primary, #2490ef);
    background: var(--primary-light, #e4f2ff);
}
.frai-chips-row {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    width: 100%;
}
.frai-chips-row-rtl, .frai-chips-row-ckb, .frai-chips-row-ar { direction: rtl; }
.frai-chip-rtl, .frai-chip-ckb, .frai-chip-ar { text-align: right; }
.frai-chip-badge {
    font-size: 8px;
    opacity: 0.65;
    margin-left: 4px;
}
.frai-chip-rtl .frai-chip-badge, .frai-chip-ckb .frai-chip-badge, .frai-chip-ar .frai-chip-badge { margin-left: 0; margin-right: 4px; }
#frai-locale-toggle {
    display: none;
    gap: 4px;
    margin-right: 8px;
}
#frai-locale-toggle.frai-visible { display: inline-flex; }
.frai-locale-btn {
    font-size: 10px;
    padding: 2px 8px;
    border-radius: 12px;
    border: 1px solid var(--border-color, #d1d8dd);
    background: var(--fg-color, #fff);
    color: var(--text-muted, #8d99a6);
    cursor: pointer;
}
.frai-locale-btn.frai-locale-active {
    border-color: var(--primary, #2490ef);
    color: var(--primary, #2490ef);
    font-weight: 600;
}
.frai-nav-links {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
}
.frai-nav-link {
    font-size: 11px;
    padding: 5px 10px;
    border-radius: 6px;
    border: 1px solid var(--primary, #2490ef);
    background: var(--primary-light, #e4f2ff);
    color: var(--primary, #2490ef);
    cursor: pointer;
}
.frai-nav-link:hover { background: var(--primary, #2490ef); color: #fff; }
.frai-nav-confirm {
    margin-top: 8px;
    font-size: 11.5px;
    padding: 6px 12px;
    border-radius: 6px;
    border: none;
    background: var(--primary, #2490ef);
    color: #fff;
    cursor: pointer;
    width: 100%;
    text-align: left;
}

/* ── Capability grid (coding welcome) ── */
.frai-cap-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 7px;
    padding: 0 12px 12px;
    animation: frai-in .18s ease;
}
.frai-cap-card {
    background: var(--fg-color, #fff);
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 8px;
    padding: 10px;
    cursor: pointer;
    transition: border-color .13s, box-shadow .13s, transform .12s;
    text-align: left;
}
.frai-cap-card:hover {
    border-color: var(--primary, #2490ef);
    box-shadow: 0 2px 8px rgba(36,144,239,0.12);
    transform: translateY(-1px);
}
.frai-cap-icon {
    font-size: 18px;
    display: block;
    margin-bottom: 5px;
    line-height: 1;
}
.frai-cap-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-color, #36414c);
    display: block;
}
.frai-cap-desc {
    font-size: 10.5px;
    color: var(--text-muted, #8d99a6);
    display: block;
    margin-top: 2px;
    line-height: 1.4;
}

/* ── Typing indicator ── */
#frai-typing,
#frai-typing-coding,
#frai-typing-advisor {
    display: none;
    align-self: flex-start;
    gap: 4px;
    align-items: center;
    padding: 9px 12px;
    background: var(--control-bg, #f4f5f6);
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 4px 10px 10px 10px;
}
#frai-typing.frai-visible,
#frai-typing-coding.frai-visible,
#frai-typing-advisor.frai-visible { display: flex; }
#frai-typing i,
#frai-typing-coding i,
#frai-typing-advisor i {
    display: inline-block;
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--text-muted, #8d99a6);
    animation: frai-dot .9s infinite;
    flex-shrink: 0;
}
#frai-typing i:nth-child(2),
#frai-typing-coding i:nth-child(2),
#frai-typing-advisor i:nth-child(2) { animation-delay: .15s; }
#frai-typing i:nth-child(3),
#frai-typing-coding i:nth-child(3),
#frai-typing-advisor i:nth-child(3) { animation-delay: .3s; }
@keyframes frai-dot {
    0%,80%,100% { transform:scale(.7); opacity:.4; }
    40%          { transform:scale(1);  opacity:1; }
}
.frai-typing-label {
    font-size: 11px;
    color: var(--text-muted, #8d99a6);
    margin-left: 6px;
    font-style: italic;
    transition: opacity .3s;
}

/* ── Footer ── */
#frai-footer {
    flex-shrink: 0;
    padding: 10px 12px;
    border-top: 1px solid var(--border-color, #d1d8dd);
    background: var(--fg-color, #fff);
    display: flex;
    gap: 8px;
    align-items: flex-end;
}
#frai-input {
    flex: 1;
    resize: none;
    padding: 8px 10px;
    border-radius: 8px;
    border: 1px solid var(--border-color, #d1d8dd);
    background: var(--control-bg, #f4f5f6);
    font-size: 12.5px;
    font-family: inherit;
    color: var(--text-color, #36414c);
    line-height: 1.5;
    outline: none;
    max-height: 96px;
    transition: border-color .15s, background .15s;
}
#frai-input:focus {
    border-color: var(--primary, #2490ef);
    background: var(--fg-color, #fff);
}
#frai-input::placeholder { color: var(--text-muted, #8d99a6); }
#frai-send {
    width: 34px; height: 34px;
    border-radius: 8px;
    border: none;
    background: var(--primary, #2490ef);
    color: #fff;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    transition: background .13s, transform .1s;
}
#frai-send:hover  { background: var(--primary-dark, #1a73c8); }
#frai-send:active { transform: scale(.93); }
#frai-send svg {
    width: 15px; height: 15px;
    fill: none;
    stroke: #fff;
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-linejoin: round;
}
body.frai-is-resizing * {
    cursor: ew-resize !important;
    user-select: none !important;
}

/* ── Preview card (staged, amber tint) ── */
.frai-preview-card {
    align-self: flex-start;
    width: 94%;
    background: #fffdf5;
    border: 1px solid #fde68a;
    border-radius: 8px;
    padding: 12px;
    font-size: 12px;
    line-height: 1.65;
    animation: frai-in .15s ease;
}
.frai-preview-badge {
    display: inline-block;
    font-size: 9.5px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #92400e;
    background: #fef3c7;
    border-radius: 4px;
    padding: 2px 7px;
    margin-bottom: 8px;
}
.frai-preview-body {
    color: var(--text-color, #36414c);
    margin-bottom: 2px;
}
.frai-preview-body ul {
    margin: 4px 0;
    padding-left: 16px;
}
.frai-preview-body pre {
    font-size: 10.5px;
    white-space: pre-wrap;
    background: #1a1f2e;
    color: #e2e8f0;
    padding: 8px 10px;
    border-radius: 6px;
    margin: 6px 0;
    overflow-x: auto;
    line-height: 1.5;
}
.frai-preview-actions {
    display: flex;
    gap: 6px;
    margin-top: 10px;
}
.frai-btn-apply {
    flex: 1;
    padding: 7px 10px;
    border-radius: 6px;
    border: none;
    background: #16a34a;
    color: #fff;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background .13s;
}
.frai-btn-apply:hover    { background: #15803d; }
.frai-btn-apply:disabled { background: #86efac; cursor: not-allowed; }
.frai-btn-cancel {
    padding: 7px 12px;
    border-radius: 6px;
    border: 1px solid var(--border-color, #d1d8dd);
    background: var(--fg-color, #fff);
    color: var(--text-muted, #6b7280);
    font-size: 12px;
    cursor: pointer;
    transition: background .13s;
}
.frai-btn-cancel:hover { background: var(--control-bg, #f4f5f6); }

/* ── Success card (green tint + checkmark) ── */
.frai-success-card {
    align-self: flex-start;
    width: 94%;
    background: #f6ffed;
    border: 1px solid #b7eb8f;
    border-radius: 8px;
    padding: 12px;
    font-size: 12px;
    line-height: 1.6;
    animation: frai-in .15s ease;
}
.frai-success-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 5px;
}
.frai-check-circle {
    width: 22px; height: 22px;
    border-radius: 50%;
    background: #16a34a;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.frai-check-svg { width: 11px; height: 11px; }
.frai-check-path {
    stroke: #fff;
    stroke-width: 2.5;
    stroke-linecap: round;
    stroke-linejoin: round;
    fill: none;
    stroke-dasharray: 20;
    stroke-dashoffset: 20;
    animation: frai-check-draw 0.4s ease forwards 0.15s;
}
@keyframes frai-check-draw {
    to { stroke-dashoffset: 0; }
}
.frai-success-title {
    font-size: 12px;
    font-weight: 700;
    color: #15803d;
}
.frai-success-detail {
    font-size: 11.5px;
    color: var(--text-color, #36414c);
    margin-bottom: 6px;
}
.frai-suggestion-pill {
    display: inline-block;
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 20px;
    border: 1px dashed var(--primary, #2490ef);
    color: var(--primary, #2490ef);
    background: var(--primary-light, #e4f2ff);
    cursor: pointer;
    margin-top: 2px;
    margin-bottom: 6px;
    transition: background .12s;
    line-height: 1.5;
}
.frai-suggestion-pill:hover { background: #d0e8fa; }
.frai-success-actions {
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid #b7eb8f;
    display: flex;
    gap: 6px;
    align-items: center;
}
.frai-btn-reload {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 5px;
    border: 1px solid #bbf7d0;
    background: #fff;
    color: #15803d;
    cursor: pointer;
    transition: background .12s;
}
.frai-btn-reload:hover { background: #dcfce7; }
.frai-btn-undo {
    font-size: 11px;
    padding: 4px 10px;
    border-radius: 5px;
    border: 1px solid var(--border-color, #d1d8dd);
    background: transparent;
    color: var(--text-muted, #8d99a6);
    cursor: pointer;
    transition: color .12s, border-color .12s;
}
.frai-btn-undo:hover:not(:disabled) {
    color: var(--red, #e74c3c);
    border-color: var(--red, #e74c3c);
}
.frai-btn-undo:disabled { opacity: 0.45; cursor: not-allowed; }

/* ── History tab ── */
.frai-history-list {
    flex: 1;
    overflow-y: auto;
    padding: 12px;
    display: flex;
    flex-direction: column;
    gap: 6px;
}
.frai-history-list::-webkit-scrollbar { width: 4px; }
.frai-history-list::-webkit-scrollbar-track { background: transparent; }
.frai-history-list::-webkit-scrollbar-thumb {
    background: var(--border-color, #d1d8dd);
    border-radius: 4px;
}
.frai-history-empty {
    text-align: center;
    padding: 40px 16px;
    color: var(--text-muted, #8d99a6);
    font-size: 12.5px;
    line-height: 1.6;
}
.frai-history-empty svg {
    display: block;
    margin: 0 auto 12px;
    opacity: 0.28;
}
.frai-history-loading {
    text-align: center;
    padding: 30px;
    color: var(--text-muted, #8d99a6);
    font-size: 12px;
}
.frai-history-item {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 9px 10px;
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 8px;
    font-size: 12px;
    animation: frai-in .12s ease;
}
.frai-history-item.frai-rolled-back { opacity: 0.48; }
.frai-history-badge {
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    padding: 2px 6px;
    border-radius: 4px;
    flex-shrink: 0;
    white-space: nowrap;
}
.frai-hb-doctype   { background: #e0e7ff; color: #3730a3; }
.frai-hb-field     { background: #fef3c7; color: #b45309; }
.frai-hb-script    { background: #f0fdf4; color: #15803d; }
.frai-hb-workflow  { background: #fdf4ff; color: #7e22ce; }
.frai-hb-documents { background: #f0f9ff; color: #0369a1; }
.frai-history-info {
    flex: 1;
    min-width: 0;
}
.frai-history-name {
    font-weight: 500;
    color: var(--text-color, #36414c);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}
.frai-history-meta {
    font-size: 10.5px;
    color: var(--text-muted, #8d99a6);
    margin-top: 1px;
}
.frai-history-undo-btn {
    flex-shrink: 0;
    font-size: 11px;
    padding: 3px 9px;
    border-radius: 5px;
    border: 1px solid var(--border-color, #d1d8dd);
    background: transparent;
    color: var(--text-muted, #8d99a6);
    cursor: pointer;
    transition: color .12s, border-color .12s;
}
.frai-history-undo-btn:hover:not(:disabled) {
    color: var(--red, #e74c3c);
    border-color: var(--red, #e74c3c);
}
.frai-history-undo-btn:disabled { opacity: 0.42; cursor: not-allowed; }
.frai-history-rolled-label {
    font-size: 10px;
    color: var(--text-muted, #8d99a6);
    font-style: italic;
    flex-shrink: 0;
}

/* ── API setup empty state (full takeover) ── */
.frai-setup-mode #frai-tabs,
.frai-setup-mode #frai-subtabs {
    display: none !important;
}
.frai-setup-mode #frai-header {
    border-bottom: none;
}
.frai-setup-mode #frai-body > .frai-tab-pane {
    display: none !important;
    visibility: hidden;
    pointer-events: none;
}
.frai-setup-mode #frai-footer {
    display: none !important;
}
#frai-body { position: relative; overflow: hidden; }
.frai-api-setup {
    position: absolute;
    inset: 0;
    z-index: 20;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 28px 22px 24px;
    background: var(--fg-color, #fff);
    animation: frai-setup-in 0.4s cubic-bezier(0.22, 1, 0.36, 1);
    overflow-y: auto;
}
.frai-api-setup::before {
    content: "";
    position: absolute;
    inset: 0;
    background:
        radial-gradient(ellipse 80% 50% at 50% -10%, rgba(36, 144, 239, 0.09) 0%, transparent 55%),
        radial-gradient(ellipse 60% 40% at 100% 100%, rgba(36, 144, 239, 0.05) 0%, transparent 50%);
    pointer-events: none;
}
@keyframes frai-setup-in {
    from { opacity: 0; transform: translateY(12px) scale(0.98); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
.frai-api-setup-inner {
    position: relative;
    width: 100%;
    max-width: 300px;
    text-align: center;
}
.frai-api-setup-icon {
    width: 64px;
    height: 64px;
    margin: 0 auto 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(145deg, var(--primary, #2490ef) 0%, #5b9cf5 100%);
    color: #fff;
    box-shadow: 0 8px 28px rgba(36, 144, 239, 0.28);
    animation: frai-setup-pulse 3s ease-in-out infinite;
}
@keyframes frai-setup-pulse {
    0%, 100% { box-shadow: 0 8px 28px rgba(36, 144, 239, 0.28); }
    50%      { box-shadow: 0 10px 36px rgba(36, 144, 239, 0.38); }
}
.frai-api-setup-icon svg {
    width: 28px;
    height: 28px;
    stroke: currentColor;
    fill: none;
    stroke-width: 1.8;
}
.frai-api-setup-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--text-color, #36414c);
    margin-bottom: 8px;
    line-height: 1.3;
    letter-spacing: -0.01em;
}
.frai-api-setup-desc {
    font-size: 12.5px;
    color: var(--text-muted, #8d99a6);
    line-height: 1.6;
    margin-bottom: 22px;
}
.frai-api-setup-steps {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 22px;
    text-align: left;
}
.frai-api-setup-step {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 11.5px;
    color: var(--text-color, #36414c);
    padding: 8px 10px;
    border-radius: 8px;
    background: var(--control-bg, #f4f5f6);
    border: 1px solid var(--border-color, #e8ecef);
}
.frai-api-setup-step-num {
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: var(--primary-light, #e4f2ff);
    color: var(--primary, #2490ef);
    font-size: 10px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
}
.frai-api-setup-cta {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    width: 100%;
    padding: 11px 16px;
    border: none;
    border-radius: 9px;
    background: var(--primary, #2490ef);
    color: #fff;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
    box-shadow: 0 3px 12px rgba(36, 144, 239, 0.35);
}
.frai-api-setup-cta:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(36, 144, 239, 0.42);
}
.frai-api-setup-secondary {
    font-size: 11px;
    color: var(--text-muted, #8d99a6);
    margin-top: 16px;
    line-height: 1.55;
}
.frai-api-setup-providers {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    margin-top: 20px;
    padding-top: 18px;
    border-top: 1px solid var(--border-color, #e8ecef);
}
.frai-api-setup-providers span {
    font-size: 10px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 20px;
    background: var(--control-bg, #eef0f2);
    color: var(--text-muted, #8d99a6);
    border: 1px solid transparent;
    transition: border-color 0.15s, color 0.15s, background 0.15s;
}
.frai-api-setup-providers span.frai-provider-active {
    background: var(--primary-light, #e4f2ff);
    color: var(--primary, #2490ef);
    border-color: rgba(36, 144, 239, 0.25);
    font-weight: 600;
}
#frai-settings-gear {
    display: none;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    flex-shrink: 0;
    border: none;
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted, #8d99a6);
    cursor: pointer;
    padding: 0;
    transition: color .12s, background .12s, box-shadow .12s;
}
#frai-settings-gear:hover {
    color: var(--primary, #2490ef);
    background: var(--primary-light, #e4f2ff);
    box-shadow: 0 0 0 3px var(--primary-light, #e4f2ff);
}
#frai-settings-gear svg {
    width: 16px;
    height: 16px;
    stroke: currentColor;
    fill: none;
    stroke-width: 2;
}
    `;
    document.head.appendChild(style);
}


// ════════════════════════════════════════════════════════════════
// DOM
// ════════════════════════════════════════════════════════════════
function _buildDOM() {

    var trigger = document.createElement("button");
    trigger.id = "frai-trigger";
    trigger.type = "button";
    trigger.className = "frai-trigger-pulse";
    trigger.setAttribute("title", "Open Frappe Pilot");
    trigger.setAttribute("aria-controls", "frai-panel");
    trigger.setAttribute("aria-expanded", "false");
    trigger.innerHTML =
        '<span class="frai-trigger-rail">' +
            '<span class="frai-trigger-beam" aria-hidden="true"></span>' +
            '<span class="frai-trigger-icon" aria-hidden="true">' +
                '<svg viewBox="0 0 24 24">' +
                    '<path d="M12 2l1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5z"/>' +
                    '<path d="M19 2l.75 2.25L22 5l-2.25.75L19 8l-.75-2.25L16 5l2.25-.75z"/>' +
                '</svg>' +
            '</span>' +
            '<span class="frai-trigger-copy">' +
                '<span id="frai-trigger-label">Pilot</span>' +
            '</span>' +
        '</span>';
    document.body.appendChild(trigger);

    setTimeout(function () {
        if (trigger) trigger.classList.remove("frai-trigger-pulse");
    }, 12000);

    var panel = document.createElement("div");
    panel.id = "frai-panel";
    panel.setAttribute("role", "complementary");
    panel.setAttribute("aria-label", "Frappe Pilot");
    panel.innerHTML =

        '<div id="frai-resize-handle" title="Drag to resize"></div>' +

        '<div id="frai-header">' +
            '<div id="frai-header-row">' +
                '<div id="frai-icon-wrap">' +
                    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
                        '<path d="M12 2l1.5 6.5L20 10l-6.5 1.5L12 18l-1.5-6.5L4 10l6.5-1.5z"/>' +
                        '<path d="M19 2l.75 2.25L22 5l-2.25.75L19 8l-.75-2.25L16 5l2.25-.75z"/>' +
                    '</svg>' +
                '</div>' +
                '<div id="frai-title-wrap">' +
                    '<div id="frai-title">Frappe Pilot</div>' +
                    '<div id="frai-subtitle">Loading…</div>' +
                '</div>' +
                '<div id="frai-header-controls">' +
                    '<button id="frai-settings-gear" type="button" aria-label="Pilot Settings" title="Pilot Settings">' +
                        '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/>' +
                        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' +
                        '</svg>' +
                    '</button>' +
                    '<button id="frai-close" aria-label="Close">&#10005;</button>' +
                '</div>' +
            '</div>' +
            '<div id="frai-header-actions">' +
                '<div id="frai-position-toggle">' +
                    '<button type="button" class="frai-position-btn frai-position-active" data-position="right" title="Dock right">' +
                        '<svg viewBox="0 0 20 20"><rect x="12" y="3" width="5" height="14" rx="1"/><rect x="3" y="3" width="7" height="14" rx="1" opacity=".35"/></svg>' +
                    '</button>' +
                    '<button type="button" class="frai-position-btn" data-position="left" title="Dock left">' +
                        '<svg viewBox="0 0 20 20"><rect x="3" y="3" width="5" height="14" rx="1"/><rect x="10" y="3" width="7" height="14" rx="1" opacity=".35"/></svg>' +
                    '</button>' +
                    '<button type="button" class="frai-position-btn" data-position="bottom" title="Dock bottom">' +
                        '<svg viewBox="0 0 20 20"><rect x="3" y="12" width="14" height="5" rx="1"/><rect x="3" y="3" width="14" height="7" rx="1" opacity=".35"/></svg>' +
                    '</button>' +
                    '<button type="button" class="frai-position-reset" id="frai-position-reset" title="Reset to site default">&#8634;</button>' +
                '</div>' +
                '<div id="frai-locale-toggle"></div>' +
            '</div>' +
            '<div id="frai-tabs">' +
                '<button class="frai-tab frai-tab-active" data-tab="advisor">Advisor</button>' +
                '<button class="frai-tab" data-tab="build">Build</button>' +
            '</div>' +
            '<div id="frai-subtabs">' +
                '<button class="frai-subtab frai-subtab-active" data-subtab="chat">Chat</button>' +
                '<button class="frai-subtab" data-subtab="changes">Changes</button>' +
            '</div>' +
        '</div>' +

        '<div id="frai-body">' +

            '<div id="frai-pane-advisor" class="frai-tab-pane frai-pane-active">' +
                '<div id="frai-messages-advisor" class="frai-messages-area">' +
                    '<div id="frai-typing-advisor"><i></i><i></i><i></i>' +
                        '<span class="frai-typing-label">Analyzing…</span>' +
                    '</div>' +
                '</div>' +
            '</div>' +

            '<div id="frai-pane-coding" class="frai-tab-pane">' +
                '<div id="frai-messages-coding" class="frai-messages-area">' +
                    '<div id="frai-typing-coding"><i></i><i></i><i></i>' +
                        '<span class="frai-typing-label">Thinking…</span>' +
                    '</div>' +
                '</div>' +
            '</div>' +

            '<div id="frai-pane-history" class="frai-tab-pane">' +
                '<div id="frai-history-list" class="frai-history-list">' +
                    '<div class="frai-history-loading">Loading…</div>' +
                '</div>' +
            '</div>' +

        '</div>' +

        '<div id="frai-footer">' +
            '<textarea id="frai-input" rows="1" ' +
                'placeholder="" ' +
                'aria-label="Message input"></textarea>' +
            '<button id="frai-send" aria-label="Send">' +
                '<svg viewBox="0 0 24 24">' +
                    '<line x1="22" y1="2" x2="11" y2="13"/>' +
                    '<polygon points="22 2 15 22 11 13 2 9 22 2"/>' +
                '</svg>' +
            '</button>' +
        '</div>';

    document.body.appendChild(panel);
}


// ════════════════════════════════════════════════════════════════
// SIDEBAR POSITION
// ════════════════════════════════════════════════════════════════
function _applySidebarPosition(pos) {
    pos = pos || FRAI.sidebarPosition || "right";
    if (pos !== "right" && pos !== "left" && pos !== "bottom") pos = "right";
    FRAI.sidebarPosition = pos;

    var panel = document.getElementById("frai-panel");
    var trigger = document.getElementById("frai-trigger");
    if (!panel || !trigger) return;

    ["right", "left", "bottom"].forEach(function (p) {
        panel.classList.remove("frai-pos-" + p);
        trigger.classList.remove("frai-pos-" + p);
    });
    panel.classList.add("frai-pos-" + pos);
    trigger.classList.add("frai-pos-" + pos);

    panel.style.width = "";
    panel.style.height = "";

    if (pos === "bottom") {
        FRAI.panelHeight = FRAI.panelHeight || _loadPanelHeight();
        panel.style.height = FRAI.panelHeight + "px";
    } else {
        FRAI.panelWidth = FRAI.panelWidth || _loadPanelWidth();
        panel.style.width = FRAI.panelWidth + "px";
    }

    _syncTriggerOffset();
    _syncPositionToggle();
}

function _syncTriggerOffset() {
    var trigger = document.getElementById("frai-trigger");
    if (!trigger) return;
    var pos = FRAI.sidebarPosition || "right";
    var edge = "0px";

    if (FRAI.isOpen) {
        if (pos === "right" || pos === "left") {
            edge = FRAI.panelWidth + "px";
        } else {
            edge = (FRAI.panelHeight || _loadPanelHeight()) + "px";
        }
    }

    trigger.style.setProperty("--frai-trigger-edge", edge);
}

function _syncPositionToggle() {
    var pos = FRAI.sidebarPosition || "right";
    var titles = { right: "position_right", left: "position_left", bottom: "position_bottom" };

    document.querySelectorAll("#frai-position-toggle .frai-position-btn").forEach(function (btn) {
        btn.classList.toggle("frai-position-active", btn.dataset.position === pos);
        var key = titles[btn.dataset.position];
        if (key) btn.setAttribute("title", _ui(key));
    });

    var reset = document.getElementById("frai-position-reset");
    if (reset) {
        reset.classList.toggle("frai-visible", _hasPositionOverride());
        reset.setAttribute("title", _ui("position_reset_default"));
    }
}

function _setSidebarPosition(pos, persist) {
    if (pos !== "right" && pos !== "left" && pos !== "bottom") pos = "right";
    if (persist) _saveSidebarPositionOverride(pos);
    _applySidebarPosition(pos);
}

function _resetSidebarPositionToSiteDefault() {
    _clearSidebarPositionOverride();
    _applySidebarPosition(_resolveSidebarPosition());
}


// ════════════════════════════════════════════════════════════════
// RESIZE
// ════════════════════════════════════════════════════════════════
function _bindResizeEvents() {
    var handle = document.getElementById("frai-resize-handle");
    var panel  = document.getElementById("frai-panel");
    if (!handle || !panel) return;

    handle.addEventListener("mousedown", function (e) {
        e.preventDefault();
        var trigger = document.getElementById("frai-trigger");
        FRAI.isResizing = true;
        panel.classList.add("frai-resizing");
        if (trigger) trigger.classList.add("frai-resizing");
        handle.classList.add("frai-dragging");
        document.body.classList.add("frai-is-resizing");

        var startX = e.clientX;
        var startY = e.clientY;
        var startWidth = panel.offsetWidth;
        var startHeight = panel.offsetHeight;
        var pos = FRAI.sidebarPosition || "right";

        function onMouseMove(e) {
            if (!FRAI.isResizing) return;
            if (pos === "bottom") {
                var maxH = Math.round(window.innerHeight * PANEL_HEIGHT_MAX_VH);
                var newHeight = Math.min(maxH, Math.max(PANEL_HEIGHT_MIN, startHeight + (startY - e.clientY)));
                FRAI.panelHeight = newHeight;
                panel.style.height = newHeight + "px";
                _savePanelHeight(newHeight);
            } else if (pos === "left") {
                var newWidthL = Math.min(PANEL_WIDTH_MAX, Math.max(PANEL_WIDTH_MIN, startWidth + (e.clientX - startX)));
                FRAI.panelWidth = newWidthL;
                panel.style.width = newWidthL + "px";
                _savePanelWidth(newWidthL);
            } else {
                var newWidthR = Math.min(PANEL_WIDTH_MAX, Math.max(PANEL_WIDTH_MIN, startWidth + (startX - e.clientX)));
                FRAI.panelWidth = newWidthR;
                panel.style.width = newWidthR + "px";
                _savePanelWidth(newWidthR);
            }
            if (FRAI.isOpen) _syncTriggerOffset();
        }
        function onMouseUp() {
            FRAI.isResizing = false;
            panel.classList.remove("frai-resizing");
            if (trigger) trigger.classList.remove("frai-resizing");
            handle.classList.remove("frai-dragging");
            document.body.classList.remove("frai-is-resizing");
            document.removeEventListener("mousemove", onMouseMove);
            document.removeEventListener("mouseup",   onMouseUp);
        }
        document.addEventListener("mousemove", onMouseMove);
        document.addEventListener("mouseup",   onMouseUp);
    });
}


// ════════════════════════════════════════════════════════════════
// EVENTS
// ════════════════════════════════════════════════════════════════
function _bindEvents() {

    var triggerEl = document.getElementById("frai-trigger");
    var closeEl   = document.getElementById("frai-close");
    var sendEl    = document.getElementById("frai-send");
    var inputEl   = document.getElementById("frai-input");

    var gearEl = document.getElementById("frai-settings-gear");

    if (triggerEl) triggerEl.addEventListener("click", togglePanel);
    if (closeEl)   closeEl.addEventListener("click", closePanel);
    if (sendEl)    sendEl.addEventListener("click", sendMessage);
    if (gearEl)    gearEl.addEventListener("click", _openPilotSettings);

    document.querySelectorAll("#frai-tabs .frai-tab").forEach(function (btn) {
        btn.addEventListener("click", function () { switchTab(btn.dataset.tab); });
    });

    document.querySelectorAll("#frai-subtabs .frai-subtab").forEach(function (btn) {
        btn.addEventListener("click", function () { switchBuildSubtab(btn.dataset.subtab); });
    });

    document.querySelectorAll("#frai-position-toggle .frai-position-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
            _setSidebarPosition(btn.dataset.position || "right", true);
        });
    });

    var posReset = document.getElementById("frai-position-reset");
    if (posReset) posReset.addEventListener("click", _resetSidebarPositionToSiteDefault);

    if (inputEl) {
        inputEl.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                sendMessage();
            }
        });
        inputEl.addEventListener("input", function () {
            this.style.height = "auto";
            this.style.height = Math.min(this.scrollHeight, 96) + "px";
        });
    }

    if (frappe.router) {
        frappe.router.on("change", _scheduleContextOnNavigate);
    }

    $(document).on("page-change form-refresh form-load form-rename", function () {
        _scheduleContextOnNavigate();
    });

    window.addEventListener("hashchange", _scheduleContextOnNavigate);
}

function _scheduleContextCheck() {
    _scheduleContextOnNavigate();
}

function _scheduleContextOnNavigate() {
    clearTimeout(FRAI._ctxTimer1);
    clearTimeout(FRAI._ctxTimer2);
    clearTimeout(FRAI._ctxTimer3);
    clearTimeout(FRAI._ctxTimer4);

    _updateContext();
    FRAI._ctxTimer1 = setTimeout(_updateContext, 250);
    FRAI._ctxTimer2 = setTimeout(_updateContext, 600);
    FRAI._ctxTimer3 = setTimeout(_updateContext, 1200);
    FRAI._ctxTimer4 = setTimeout(_updateContext, 2000);
}


// ════════════════════════════════════════════════════════════════
// PILOT CONFIG / API SETUP
// ════════════════════════════════════════════════════════════════
function _hasApiKey() {
    return FRAI.config && FRAI.config.has_api_key;
}

function _isApiSetupMode() {
    return FRAI.apiSetupActive === true;
}

function _canSendMessage() {
    return _hasApiKey() && FRAI.config && FRAI.config.can_access_pilot !== false;
}

function _providerChipClass(name, active) {
    return name === active ? " frai-provider-active" : "";
}

function _openPilotSettings() {
    frappe.set_route("Form", "Pilot Settings", "Pilot Settings");
}

function _applyTabVisibility() {
    var cfg = FRAI.config || {};
    var buildTab = document.querySelector('#frai-tabs .frai-tab[data-tab="build"]');
    if (buildTab) {
        var showBuild = cfg.build_enabled !== false && cfg.can_access_build;
        buildTab.style.display = showBuild ? "" : "none";
    }
    if (cfg.default_tab && _hasApiKey()) {
        var t = cfg.default_tab;
        if (t === "analyze" || t === "guide") t = "advisor";
        if (t === "build" && buildTab && buildTab.style.display === "none") {
            t = "advisor";
        }
        FRAI.activeTab = t;
        switchTab(t);
    }
}

function _showApiSetupState() {
    _hideApiSetupState();
    var body = document.getElementById("frai-body");
    var panel = document.getElementById("frai-panel");
    var subtitle = document.getElementById("frai-subtitle");
    if (!body || !panel) return;

    FRAI.apiSetupActive = true;

    var cfg = FRAI.config || {};
    var canConfig = cfg.can_configure_api;
    var provider = cfg.active_provider || "Groq";

    if (subtitle) {
        if (!FRAI._savedSubtitle) FRAI._savedSubtitle = subtitle.textContent;
        subtitle.textContent = "Setup required — connect an AI provider";
    }

    var ctaHtml = canConfig
        ? '<button type="button" class="frai-api-setup-cta" id="frai-api-setup-btn">' +
          '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
          '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>' +
          '</svg> ' + _ui("setup_cta") + '</button>'
        : "";

    var stepsHtml = canConfig
        ? '<div class="frai-api-setup-steps">' +
            '<div class="frai-api-setup-step"><span class="frai-api-setup-step-num">1</span>Open Pilot Settings</div>' +
            '<div class="frai-api-setup-step"><span class="frai-api-setup-step-num">2</span>Add your ' + provider + ' API key</div>' +
            '<div class="frai-api-setup-step"><span class="frai-api-setup-step-num">3</span>Test connection and save</div>' +
          '</div>'
        : "";

    var secondary = canConfig
        ? _ui("setup_secondary_sm")
        : _ui("setup_secondary_user");

    var wrap = document.createElement("div");
    wrap.id = "frai-api-setup";
    wrap.className = "frai-api-setup";
    wrap.setAttribute("role", "region");
    wrap.setAttribute("aria-label", "Pilot API setup");
    wrap.innerHTML =
        '<div class="frai-api-setup-inner">' +
            '<div class="frai-api-setup-icon">' +
                '<svg viewBox="0 0 24 24"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/>' +
                '</svg>' +
            '</div>' +
            '<div class="frai-api-setup-title">' + _ui("setup_title") + '</div>' +
            '<div class="frai-api-setup-desc">' + _ui("setup_desc") + '</div>' +
            stepsHtml +
            ctaHtml +
            '<div class="frai-api-setup-secondary">' + secondary + '</div>' +
            '<div class="frai-api-setup-providers">' +
                '<span class="' + _providerChipClass("Groq", provider).trim() + '">Groq</span>' +
                '<span class="' + _providerChipClass("OpenAI", provider).trim() + '">OpenAI</span>' +
                '<span class="' + _providerChipClass("Gemini", provider).trim() + '">Gemini</span>' +
            '</div>' +
        '</div>';

    body.appendChild(wrap);
    panel.classList.add("frai-setup-mode");

    var btn = document.getElementById("frai-api-setup-btn");
    if (btn) btn.addEventListener("click", _openPilotSettings);
}

function _hideApiSetupState() {
    var el = document.getElementById("frai-api-setup");
    var panel = document.getElementById("frai-panel");
    var subtitle = document.getElementById("frai-subtitle");

    FRAI.apiSetupActive = false;
    if (el) el.remove();
    if (panel) panel.classList.remove("frai-setup-mode");
    if (subtitle && FRAI._savedSubtitle) {
        subtitle.textContent = FRAI._savedSubtitle;
        FRAI._savedSubtitle = "";
    }
}

function _refreshPilotConfig(callback) {
    frappe.call({
        method: "frappe_pilot.api.config.get_pilot_config",
        callback: function (r) {
            if (r && r.message) {
                FRAI.config = r.message;
                FRAI.suggestionsCache = {};
                _normalizeSidebarLocale();
                _renderLocaleToggle();
                _applyTabVisibility();
                _applyPilotLocale();
                if (!_hasPositionOverride()) {
                    _applySidebarPosition(_resolveSidebarPosition());
                }
            }
            if (callback) callback();
        },
    });
}


// ════════════════════════════════════════════════════════════════
// PANEL OPEN / CLOSE
// ════════════════════════════════════════════════════════════════
function togglePanel() { FRAI.isOpen ? closePanel() : openPanel(); }

function _syncTriggerState() {
    var trigger = document.getElementById("frai-trigger");
    if (!trigger) return;
    trigger.classList.toggle("frai-trigger-open", !!FRAI.isOpen);
    trigger.setAttribute("aria-expanded", FRAI.isOpen ? "true" : "false");
    trigger.setAttribute(
        "aria-label",
        FRAI.isOpen ? _ui("trigger_close_label") : _ui("trigger_title")
    );
}

function openPanel() {
    FRAI.isOpen = true;
    var panel = document.getElementById("frai-panel");
    if (!panel) return;

    if (FRAI.sidebarPosition === "bottom") {
        FRAI.panelHeight = FRAI.panelHeight || _loadPanelHeight();
        panel.style.height = FRAI.panelHeight + "px";
    } else {
        panel.style.width = FRAI.panelWidth + "px";
    }
    panel.classList.add("frai-open");
    _syncTriggerState();
    _syncTriggerOffset();

    _refreshPilotConfig(function () {
        if (!_hasApiKey()) {
            _showApiSetupState();
            return;
        }
        _hideApiSetupState();
        _showActiveWelcome();
        var inputEl = document.getElementById("frai-input");
        if (inputEl) inputEl.focus();
    });
}

function closePanel() {
    FRAI.isOpen = false;
    var panel = document.getElementById("frai-panel");
    if (panel) panel.classList.remove("frai-open");
    _syncTriggerState();
    _syncTriggerOffset();
}


// ════════════════════════════════════════════════════════════════
// TAB SWITCHING
// ════════════════════════════════════════════════════════════════
function switchTab(tab) {
    if (tab === "analyze" || tab === "guide") tab = "advisor";
    if (!_hasApiKey()) {
        FRAI.activeTab = tab;
        if (FRAI.isOpen) _showApiSetupState();
        return;
    }

    FRAI.activeTab = tab;

    document.querySelectorAll("#frai-tabs .frai-tab").forEach(function (b) {
        b.classList.toggle("frai-tab-active", b.dataset.tab === tab);
    });

    var subtabs = document.getElementById("frai-subtabs");
    if (subtabs) {
        subtabs.classList.toggle("frai-subtabs-visible", tab === "build");
    }

    if (tab === "build") {
        switchBuildSubtab(FRAI.activeBuildSubtab || "chat");
        return;
    }

    document.querySelectorAll(".frai-tab-pane").forEach(function (p) {
        p.classList.remove("frai-pane-active");
    });

    var footer = document.getElementById("frai-footer");
    var sendEl = document.getElementById("frai-send");
    if (footer) footer.style.display = "flex";
    if (sendEl) sendEl.disabled = false;

    if (FRAI.config && FRAI.config.advisor_enabled === false) {
        _addBubble("Advisor is disabled in Pilot Settings.", "frai-error");
        return;
    }

    var advisorPane = document.getElementById("frai-pane-advisor");
    if (advisorPane) advisorPane.classList.add("frai-pane-active");
    _updateInputPlaceholder();
    _showActiveWelcome();
}

function switchBuildSubtab(subtab) {
    if (!_hasApiKey()) {
        FRAI.activeTab = "build";
        FRAI.activeBuildSubtab = subtab;
        if (FRAI.isOpen) _showApiSetupState();
        return;
    }

    FRAI.activeTab = "build";
    FRAI.activeBuildSubtab = subtab;

    document.querySelectorAll("#frai-tabs .frai-tab").forEach(function (b) {
        b.classList.toggle("frai-tab-active", b.dataset.tab === "build");
    });
    document.querySelectorAll("#frai-subtabs .frai-subtab").forEach(function (b) {
        b.classList.toggle("frai-subtab-active", b.dataset.subtab === subtab);
    });

    var subtabs = document.getElementById("frai-subtabs");
    if (subtabs) subtabs.classList.add("frai-subtabs-visible");

    document.querySelectorAll(".frai-tab-pane").forEach(function (p) {
        p.classList.remove("frai-pane-active");
    });

    var footer = document.getElementById("frai-footer");
    var input  = document.getElementById("frai-input");
    var sendEl = document.getElementById("frai-send");

    if (subtab === "changes") {
        var historyPane = document.getElementById("frai-pane-history");
        if (historyPane) historyPane.classList.add("frai-pane-active");
        if (footer) footer.style.display = "none";
        _loadHistory();
        return;
    }

    if (FRAI.config && (!FRAI.config.build_enabled || !FRAI.config.can_access_build)) {
        _addBubble("Build is disabled or you do not have permission.", "frai-error");
        return;
    }

    var buildPane = document.getElementById("frai-pane-coding");
    if (buildPane) buildPane.classList.add("frai-pane-active");
    if (footer) footer.style.display = "flex";
    if (input)  { input.disabled = false; _updateInputPlaceholder(); }
    if (sendEl) sendEl.disabled = false;
    _showActiveWelcome();
}

function _showActiveWelcome() {
    if (!_hasApiKey() || _isApiSetupMode()) return;

    if (FRAI.activeTab === "advisor") {
        var advisorMsgs = document.getElementById("frai-messages-advisor");
        if (advisorMsgs && advisorMsgs.querySelectorAll(".frai-bubble").length === 0) {
            _showAdvisorWelcome();
        }
    } else if (FRAI.activeTab === "build" && FRAI.activeBuildSubtab !== "changes") {
        var codingMsgs = document.getElementById("frai-messages-coding");
        if (codingMsgs && codingMsgs.querySelectorAll(".frai-bubble, .frai-preview-card, .frai-success-card").length === 0) {
            _showCodingWelcome();
        }
    }
}


// ════════════════════════════════════════════════════════════════
// CONTEXT DETECTION
// ════════════════════════════════════════════════════════════════
function _getRouteArr() {
    var routeArr = [];
    if (frappe.get_route) {
        try { routeArr = frappe.get_route() || []; } catch (e) { routeArr = []; }
    }
    return routeArr;
}

function _parseFormRoute(routeArr) {
    if (routeArr[0] === "Form" && routeArr[1] && routeArr[2]) {
        return { doctype: routeArr[1], docname: routeArr[2] };
    }
    return null;
}

function _collectPageContext() {
    var ctx = {
        page_type:    "other",
        report_name:  "",
        report_filters: {},
        list_doctype: "",
        list_filters: [],
        list_fields:  [],
    };

    var routeArr = _getRouteArr();

    if (routeArr[0] === "List" && routeArr[1]) {
        ctx.page_type = "list";
        ctx.list_doctype = routeArr[1];
    } else if (frappe.cur_frm && frappe.cur_frm.doctype) {
        ctx.page_type = "form";
        return ctx;
    } else if (routeArr[0] === "Form" && routeArr[1] && routeArr[2]) {
        ctx.page_type = "form";
        return ctx;
    }

    if (typeof frappe !== "undefined" && frappe.query_report && frappe.query_report.report_name) {
        ctx.page_type = "report";
        ctx.report_name = frappe.query_report.report_name;
        try {
            if (frappe.query_report.get_filter_values) {
                ctx.report_filters = frappe.query_report.get_filter_values() || {};
            }
        } catch (e) {}
        return ctx;
    }

    if (routeArr[0] === "query-report" && routeArr[1]) {
        ctx.page_type = "report";
        ctx.report_name = routeArr[1];
        if (typeof frappe !== "undefined" && frappe.query_report && frappe.query_report.get_filter_values) {
            try {
                ctx.report_filters = frappe.query_report.get_filter_values() || {};
            } catch (e) {}
        }
        return ctx;
    }

    if (routeArr[0] === "List" && routeArr[1]) {
        ctx.page_type = "list";
        ctx.list_doctype = routeArr[1];
    } else if (typeof cur_list !== "undefined" && cur_list && cur_list.doctype) {
        ctx.page_type = "list";
        ctx.list_doctype = cur_list.doctype;
    }

    if (ctx.page_type === "list") {
        if (typeof cur_list !== "undefined" && cur_list) {
            try {
                if (cur_list.get_filters_for_args) {
                    ctx.list_filters = cur_list.get_filters_for_args() || [];
                }
                if (cur_list.columns && cur_list.columns.length) {
                    ctx.list_fields = cur_list.columns.map(function (c) {
                        return c.field || c.fieldname || c;
                    }).filter(Boolean);
                } else if (cur_list.get_fields_in_list_view) {
                    ctx.list_fields = cur_list.get_fields_in_list_view() || [];
                }
            } catch (e) {}
        }
        return ctx;
    }

    return ctx;
}

function _resolveAnalyzeMode(message) {
    var text = (message || "").trim().toLowerCase();
    if (ANALYZE_DIAGNOSE_CHIPS[message] || text.indexOf("diagnose ") === 0) {
        return "diagnose";
    }
    if (text === "what's wrong" || text === "what is wrong" || text.indexOf("what's wrong") > -1) {
        return "diagnose";
    }
    return FRAI.analyzeMode || "explain";
}

function _resolveFormContext() {
    FRAI.listDoctype = null;
    FRAI.route       = "";
    var routeArr = _getRouteArr();

    if (routeArr.length >= 2 && routeArr[0] === "List" && routeArr[1]) {
        FRAI.doctype = null;
        FRAI.docname = null;
        FRAI.isNew   = false;
        FRAI.listDoctype = routeArr[1];
        FRAI.route = routeArr.join(" > ");
        return;
    }

    if (frappe.cur_frm && frappe.cur_frm.doctype) {
        FRAI.doctype = frappe.cur_frm.doctype;
        FRAI.docname = frappe.cur_frm.docname;
        FRAI.isNew   = frappe.cur_frm.is_new();
        FRAI.route = routeArr.length ? routeArr.join(" > ") : "";
        return;
    }

    var parsed = _parseFormRoute(routeArr);
    if (parsed) {
        FRAI.doctype = parsed.doctype;
        FRAI.docname = parsed.docname;
        FRAI.isNew   = false;
        FRAI.route = routeArr.join(" > ");
        return;
    }

    FRAI.doctype = null;
    FRAI.docname = null;
    FRAI.isNew   = false;

    var route = routeArr.length ? routeArr.join(" > ") : "";
    if (!route && frappe.get_route_str) {
        try { route = frappe.get_route_str() || ""; } catch (e) {}
    }
    if (!route) {
        route = (window.location.hash || "").replace(/^#\/?/, "") || "Home";
    }
    FRAI.route = route;
}

function _updateContext() {
    var subtitle = document.getElementById("frai-subtitle");
    if (!subtitle) return;

    _resolveFormContext();

    if (FRAI.doctype) {
        subtitle.textContent = FRAI.doctype + ": " + (FRAI.isNew ? "(New)" : (FRAI.docname || ""));
    } else if (FRAI.listDoctype) {
        subtitle.textContent = FRAI.listDoctype + " List";
    } else {
        var routeArr = _getRouteArr();
        subtitle.textContent = _buildSubtitleLabel(routeArr, FRAI.route);
    }

    var ctxKey = (FRAI.doctype || "") + "|" + (FRAI.docname || "") + "|" +
                 (FRAI.listDoctype || "") + "|" + (FRAI.route || "");
    if (FRAI.lastContextKey && FRAI.lastContextKey !== ctxKey) {
        FRAI.suggestionsCache = {};
        if (_hasApiKey() && !_isApiSetupMode()) {
            _resetChatPane("frai-messages-advisor", _showAdvisorWelcome);
            if (FRAI.activeTab === "build") {
                _resetChatPane("frai-messages-coding", _showCodingWelcome);
            }
        }
    }
    FRAI.lastContextKey = ctxKey;
    _updateInputPlaceholder();

    if (FRAI.isOpen) {
        if (!_hasApiKey()) {
            _showApiSetupState();
        } else if (!_isApiSetupMode()) {
            _showActiveWelcome();
        }
    }
}

function _resetChatPane(msgsId, welcomeFn) {
    var msgs = document.getElementById(msgsId);
    if (!msgs) return;
    msgs.querySelectorAll(".frai-bubble, .frai-chips, .frai-context-hint, .frai-cap-grid").forEach(function (el) {
        el.remove();
    });
    if (welcomeFn) welcomeFn();
}

function _buildSubtitleLabel(routeArr, route) {
    if (!routeArr.length && !route) return "Home";
    if (routeArr[0] === "Form" && routeArr[1] && routeArr[2]) {
        return routeArr[1] + ": " + routeArr[2];
    }
    if (routeArr[0] === "List" && routeArr[1]) return routeArr[1] + " List";
    if ((routeArr[0] === "query-report" || routeArr[0] === "Report") && routeArr[1]) {
        return "Report: " + routeArr[1];
    }
    if (routeArr.length === 1) return routeArr[0] + " Module";
    if (routeArr[0] === "dashboard" || routeArr[0] === "Dashboard") return "Dashboard";
    if (routeArr[0] === "Workspaces" || routeArr[0] === "workspace") {
        return routeArr[1] ? routeArr[1] + " Workspace" : "Workspace";
    }
    return _routeToLabel(route);
}

function _routeToLabel(route) {
    if (!route) return "Home";
    return route.split(/[\/\s>]+/)
        .filter(function(p) { return p && p.toLowerCase() !== "list"; })
        .map(function(p) {
            return p.replace(/-/g, " ").replace(/\b\w/g, function(c) { return c.toUpperCase(); });
        })
        .join(" > ");
}


// ════════════════════════════════════════════════════════════════
// LOCALE / i18n
// ════════════════════════════════════════════════════════════════
function _getLanguageOptions() {
    if (FRAI.config && FRAI.config.language_options && FRAI.config.language_options.length) {
        return FRAI.config.language_options;
    }
    return [{ code: "en", label: "EN", name: "English", rtl: false, has_ui: true }];
}

function _enabledLocaleCodes() {
    return _getLanguageOptions().map(function (o) { return o.code; });
}

function _hasLocaleToggle() {
    return _getLanguageOptions().length > 1;
}

function _localeOption(code) {
    var opts = _getLanguageOptions();
    for (var i = 0; i < opts.length; i++) {
        if (opts[i].code === code) return opts[i];
    }
    return null;
}

function _normalizeSidebarLocale() {
    var codes = _enabledLocaleCodes();
    if (codes.indexOf(FRAI.sidebarLocale) < 0) {
        FRAI.sidebarLocale = "en";
        _saveSidebarLocale("en");
    }
}

function _renderLocaleToggle() {
    var wrap = document.getElementById("frai-locale-toggle");
    if (!wrap) return;

    wrap.innerHTML = "";
    var options = _getLanguageOptions();
    options.forEach(function (opt) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "frai-locale-btn" + (opt.code === FRAI.sidebarLocale ? " frai-locale-active" : "");
        btn.dataset.locale = opt.code;
        btn.textContent = opt.label || (opt.code || "en").toUpperCase();
        if (opt.rtl) {
            btn.setAttribute("dir", "rtl");
            btn.setAttribute("lang", opt.code);
        }
        btn.setAttribute("title", opt.name || opt.label || opt.code);
        btn.addEventListener("click", function () {
            FRAI.sidebarLocale = opt.code;
            _saveSidebarLocale(FRAI.sidebarLocale);
            _applyPilotLocale();
            FRAI.suggestionsCache = {};
            _showActiveWelcome();
        });
        wrap.appendChild(btn);
    });
    wrap.classList.toggle("frai-visible", _hasLocaleToggle());
}

function _activeUiStrings() {
    var cfg = FRAI.config || {};
    var ui = cfg.ui_strings || {};
    var loc = FRAI.sidebarLocale || "en";
    var opt = _localeOption(loc);
    if (ui[loc] && (!opt || opt.has_ui !== false)) return ui[loc];
    return ui.en || {};
}

function _ui(key) {
    var strings = _activeUiStrings();
    if (strings[key]) return strings[key];
    var en = (FRAI.config && FRAI.config.ui_strings && FRAI.config.ui_strings.en) || {};
    if (en[key]) return en[key];
    if (PLACEHOLDER_FALLBACKS[key]) return PLACEHOLDER_FALLBACKS[key];
    return key;
}

function _applyPilotLocale() {
    _renderLocaleToggle();

    var trigger = document.getElementById("frai-trigger-label");
    if (trigger) trigger.textContent = _ui("trigger_label");

    var triggerWrap = document.getElementById("frai-trigger");
    if (triggerWrap) {
        triggerWrap.setAttribute("title", FRAI.isOpen ? _ui("trigger_close_label") : _ui("trigger_title"));
        _syncTriggerState();
    }

    var panel = document.getElementById("frai-panel");
    if (panel) panel.setAttribute("aria-label", _ui("panel_title"));

    var advisorBtn = document.querySelector('#frai-tabs .frai-tab[data-tab="advisor"]');
    if (advisorBtn) advisorBtn.textContent = _ui("tab_advisor");
    var buildBtn = document.querySelector('#frai-tabs .frai-tab[data-tab="build"]');
    if (buildBtn) buildBtn.textContent = _ui("tab_build");

    var chatBtn = document.querySelector('#frai-subtabs .frai-subtab[data-subtab="chat"]');
    if (chatBtn) chatBtn.textContent = _ui("subtab_build_chat");
    var changesBtn = document.querySelector('#frai-subtabs .frai-subtab[data-subtab="changes"]');
    if (changesBtn) changesBtn.textContent = _ui("subtab_changes");

    var gear = document.getElementById("frai-settings-gear");
    if (gear) {
        gear.setAttribute("title", _ui("settings_gear_title"));
        gear.setAttribute("aria-label", _ui("settings_gear_title"));
    }

    _syncPositionToggle();
    _updateInputPlaceholder();
}

function _formatUiTemplate(key, vars) {
    var text = _ui(key);
    if (!vars) return text;
    return text.replace(/\{(\w+)\}/g, function (_, name) {
        var val = vars[name];
        return (val != null && val !== "") ? String(val) : "";
    }).replace(/\s{2,}/g, " ").trim();
}

function _contextFromSubtitle() {
    var sub = document.getElementById("frai-subtitle");
    if (!sub) return null;
    var text = (sub.textContent || "").trim();
    if (!text || text === "Loading…") return null;

    if (text.slice(-5) === " List") {
        return { kind: "list", doctype: text.slice(0, -5).trim(), docname: "", label: "" };
    }
    if (text.indexOf(": (New)") > 0) {
        var dtNew = text.split(":")[0].trim();
        return { kind: "form", doctype: dtNew, docname: "", label: dtNew, isNew: true };
    }
    var colon = text.indexOf(": ");
    if (colon > 0) {
        var dt = text.slice(0, colon).trim();
        var dn = text.slice(colon + 2).trim();
        return {
            kind: "form",
            doctype: dt,
            docname: dn,
            label: dn ? (dt + " " + dn) : dt,
            isNew: false,
        };
    }
    return null;
}

function _swapPlaceholderSuffix(key, fromSuffix, toSuffix) {
    if (key.slice(-fromSuffix.length) === fromSuffix) {
        return key.slice(0, -fromSuffix.length) + toSuffix;
    }
    return key;
}

function _pickPlaceholderKey() {
    var isBuild = FRAI.activeTab === "build";
    var prefix = isBuild ? "placeholder_build_" : "placeholder_advisor_";
    var ctx = _collectPageContext();
    var hint = _contextFromSubtitle();
    var onList = !!(FRAI.listDoctype || ctx.list_doctype || ctx.page_type === "list" || (hint && hint.kind === "list"));

    if (onList) return prefix + "list";
    if (!onList && (ctx.page_type === "form" || (FRAI.doctype && !FRAI.listDoctype) || (hint && hint.kind === "form"))) {
        if (!isBuild && (FRAI.isNew || (hint && hint.isNew) || (!FRAI.docname && !(hint && hint.docname)))) {
            return prefix + "form_new";
        }
        return prefix + "form";
    }
    if (!isBuild && (ctx.page_type === "report" || ctx.report_name)) {
        return prefix + "report";
    }
    return prefix + "page";
}

function _resolvePlaceholderVars() {
    var ctx = _collectPageContext();
    var hint = _contextFromSubtitle();
    var doctype = FRAI.doctype || FRAI.listDoctype || ctx.list_doctype || (hint && hint.doctype) || "";
    var docname = FRAI.isNew ? "" : (FRAI.docname || (hint && hint.docname) || "");
    var label = (hint && hint.label) || (docname ? ((doctype ? doctype + " " : "") + docname) : doctype);
    var report = ctx.report_name || "";
    if (report) report = report.replace(/-/g, " ");
    return { doctype: doctype, docname: docname, label: label, report: report };
}

function _updateInputPlaceholder() {
    var input = document.getElementById("frai-input");
    if (!input || input.disabled) return;
    if (FRAI.activeTab === "build" && FRAI.activeBuildSubtab === "changes") return;

    _resolveFormContext();

    var key = _pickPlaceholderKey();
    var vars = _resolvePlaceholderVars();

    if (key.slice(-5) === "_form" && !vars.label) {
        key = _swapPlaceholderSuffix(key, "_form", "_page");
    }
    if (key.slice(-5) === "_list" && !vars.doctype) {
        key = _swapPlaceholderSuffix(key, "_list", "_page");
    }
    if (key.slice(-7) === "_report" && !vars.report) {
        key = _swapPlaceholderSuffix(key, "_report", "_page");
    }

    var text = _formatUiTemplate(key, vars);
    if (text === key) {
        var fallbackKey = FRAI.activeTab === "build" ? "placeholder_build_page" : "placeholder_advisor_page";
        text = _formatUiTemplate(fallbackKey, vars);
    }
    input.placeholder = text;
}

// ════════════════════════════════════════════════════════════════
// CONTEXT SUGGESTIONS (server-driven chips / build actions)
// ════════════════════════════════════════════════════════════════
function _chipLocaleScope() {
    var scope = (FRAI.config && FRAI.config.chip_locale_scope) || "all_enabled";
    if (scope !== "active_locale" && scope !== "active_plus_en") return "all_enabled";
    return scope;
}

function _enabledPilotLocales() {
    return (FRAI.config && FRAI.config.languages) || ["en"];
}

function _allowedChipLocales() {
    var enabled = _enabledPilotLocales();
    var sidebarLocale = FRAI.sidebarLocale || "en";
    var scope = _chipLocaleScope();
    var allowed = {};

    if (scope === "active_locale") {
        if (enabled.indexOf(sidebarLocale) >= 0) allowed[sidebarLocale] = true;
        else allowed.en = true;
        return allowed;
    }
    if (scope === "active_plus_en") {
        allowed.en = true;
        if (sidebarLocale !== "en" && enabled.indexOf(sidebarLocale) >= 0) {
            allowed[sidebarLocale] = true;
        }
        return allowed;
    }
    enabled.forEach(function (loc) { allowed[loc] = true; });
    return allowed;
}

function _filterItemsByChipScope(items) {
    if (!items || !items.length) return [];
    var enabled = _enabledPilotLocales();
    var allowed = _allowedChipLocales();
    return items.filter(function (item) {
        var loc = (item && item.locale) || "en";
        if (enabled.indexOf(loc) < 0) return false;
        return !!allowed[loc];
    });
}

function _suggestionsCacheKey(tab) {
    var pageCtx = _collectPageContext();
    var langs = (FRAI.config && FRAI.config.languages) ? FRAI.config.languages.join(",") : "en";
    return [
        tab,
        langs,
        _chipLocaleScope(),
        FRAI.sidebarLocale || "en",
        FRAI.doctype || "",
        FRAI.isNew ? "" : (FRAI.docname || ""),
        FRAI.listDoctype || pageCtx.list_doctype || "",
        pageCtx.report_name || "",
        FRAI.route || "",
        pageCtx.page_type || "",
    ].join("|");
}

function _fetchSuggestions(tab, callback) {
    var cacheKey = _suggestionsCacheKey(tab);
    if (FRAI.suggestionsCache[cacheKey]) {
        if (callback) callback(FRAI.suggestionsCache[cacheKey]);
        return;
    }

    if (FRAI.pendingSuggestions[cacheKey]) {
        FRAI.pendingSuggestions[cacheKey].push(callback);
        return;
    }
    FRAI.pendingSuggestions[cacheKey] = callback ? [callback] : [];

    var pageCtx = _collectPageContext();
    frappe.call({
        method: "frappe_pilot.api.suggestions.get_context_suggestions",
        args: {
            tab:          tab,
            doctype:      FRAI.doctype || "",
            docname:      FRAI.isNew ? "" : (FRAI.docname || ""),
            route:        FRAI.route || "",
            list_doctype: FRAI.listDoctype || pageCtx.list_doctype || "",
            page_context: JSON.stringify(pageCtx),
            sidebar_locale: FRAI.sidebarLocale || "en",
        },
        callback: function (r) {
            var data = (r && r.message) ? r.message : _fallbackSuggestions(tab);
            FRAI.suggestionsCache[cacheKey] = data;
            var cbs = FRAI.pendingSuggestions[cacheKey] || [];
            delete FRAI.pendingSuggestions[cacheKey];
            cbs.forEach(function (cb) { if (cb) cb(data); });
        },
        error: function () {
            var data = _fallbackSuggestions(tab);
            FRAI.suggestionsCache[cacheKey] = data;
            var cbs = FRAI.pendingSuggestions[cacheKey] || [];
            delete FRAI.pendingSuggestions[cacheKey];
            cbs.forEach(function (cb) { if (cb) cb(data); });
        },
    });
}

function _isRtlLocale(locale) {
    var opt = _localeOption(locale);
    if (opt && opt.rtl) return true;
    return locale === "ckb" || locale === "ar";
}

function _detectReplyLocale(text) {
    if (!text || !text.trim()) return FRAI.replyLocale || "en";
    var langs = (FRAI.config && FRAI.config.languages) || ["en"];
    var lower = text.toLowerCase();
    if (langs.indexOf("ckb") >= 0 && /kurdish|sorani|کوردی|سۆرانی|سورانی/.test(lower)) return "ckb";
    if (/[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/.test(text)) {
        if (langs.indexOf("ckb") >= 0 && /[ۆێڵڕئۊۋ]/.test(text)) return "ckb";
        if (langs.indexOf("ar") >= 0) return "ar";
        if (langs.indexOf("ckb") >= 0) return "ckb";
    }
    return "en";
}

function _fallbackSuggestions(tab) {
    if (tab === "analyze" || tab === "guide") tab = "advisor";
    if (tab === "build") {
        return {
            greet: "What do you want to build?",
            chips: [],
            chip_meta: {},
            actions: [
                { icon: "⚙️", label: "Custom Fields", desc: "Add fields to any existing form", prompt: "Add a custom field to " },
                { icon: "📄", label: "New DocType", desc: "Create a new table from scratch", prompt: "Create a new DocType called " },
                { icon: "⚡", label: "Scripts", desc: "Python and JS automation", prompt: "Write a server script that " },
                { icon: "🔀", label: "Workflows", desc: "Approval flows with roles", prompt: "Create an approval workflow for " },
            ],
        };
    }
    return {
        greet: "Ask me anything about this page or document:",
        chips: ["Summarize this record", "Diagnose this record", "What should I do next?"],
        chip_meta: { "Diagnose this record": { mode: "diagnose" } },
        actions: [],
    };
}

function _applyChipMeta(chipMeta) {
    FRAI.chipMeta = chipMeta || {};
}

function _chipLabel(chip) {
    if (!chip) return "";
    if (typeof chip === "string") return chip;
    var label = chip.label || chip.label_primary || chip.prompt || chip.prompt_en || "";
    return typeof label === "string" ? label : String(label || "");
}

function _normalizeChip(chip) {
    if (!chip) return null;
    if (typeof chip === "string") {
        return {
            prompt: chip,
            label: chip,
            locale: "en",
            mode: ANALYZE_DIAGNOSE_CHIPS[chip] ? "diagnose" : "explain",
        };
    }
    var prompt = _chipLabel(chip);
    if (!prompt) return null;
    return {
        prompt: prompt,
        label: _chipLabel(chip),
        locale: chip.locale || "en",
        prompt_en: chip.prompt_en || "",
        mode: chip.mode || "explain",
    };
}

function _chipAnalyzeMode(chipOrPrompt) {
    if (chipOrPrompt && typeof chipOrPrompt === "object") {
        if (chipOrPrompt.mode) return chipOrPrompt.mode;
        var key = chipOrPrompt.prompt_en || chipOrPrompt.prompt;
        if (FRAI.chipMeta && FRAI.chipMeta[key] && FRAI.chipMeta[key].mode) {
            return FRAI.chipMeta[key].mode;
        }
        return ANALYZE_DIAGNOSE_CHIPS[key] ? "diagnose" : "explain";
    }
    if (FRAI.chipMeta && FRAI.chipMeta[chipOrPrompt] && FRAI.chipMeta[chipOrPrompt].mode) {
        return FRAI.chipMeta[chipOrPrompt].mode;
    }
    return ANALYZE_DIAGNOSE_CHIPS[chipOrPrompt] ? "diagnose" : "explain";
}

function _renderChips(chips, container) {
    chips = _filterItemsByChipScope(chips);
    if (!chips || !chips.length || !container) return;
    var wrap = document.createElement("div");
    wrap.className = "frai-chips";

    var rows = {};
    chips.forEach(function (raw) {
        var chip = _normalizeChip(raw);
        if (!chip || !chip.prompt) return;
        var loc = chip.locale || "en";
        if (!rows[loc]) {
            rows[loc] = document.createElement("div");
            rows[loc].className = "frai-chips-row frai-chips-row-" + loc;
            if (_isRtlLocale(loc)) rows[loc].classList.add("frai-chips-row-rtl");
        }
        var btn = document.createElement("button");
        btn.type = "button";
        var rtl = _isRtlLocale(loc);
        btn.className = "frai-chip" + (rtl ? " frai-chip-rtl frai-chip-" + loc : " frai-chip-en");
        if (rtl) {
            btn.setAttribute("dir", "rtl");
            btn.setAttribute("lang", loc);
        }
        btn.textContent = _chipLabel(chip);
        btn.addEventListener("click", function () {
            var inputEl = document.getElementById("frai-input");
            if (inputEl) inputEl.value = chip.prompt;
            FRAI.replyLocale = chip.locale || "en";
            if (FRAI.activeTab === "advisor") {
                FRAI.analyzeMode = _chipAnalyzeMode(chip);
            }
            _removeAllChips();
            sendMessage();
        });
        rows[loc].appendChild(btn);
    });

    var order = ["en"];
    var langs = (FRAI.config && FRAI.config.languages) || ["en"];
    langs.forEach(function (l) {
        if (l !== "en" && rows[l]) order.push(l);
    });
    Object.keys(rows).forEach(function (loc) {
        if (order.indexOf(loc) < 0) order.push(loc);
    });
    order.forEach(function (loc) {
        if (rows[loc] && rows[loc].childNodes.length) wrap.appendChild(rows[loc]);
    });
    container.appendChild(wrap);
}

function _renderWelcomeBubble(greet, chips, chipMeta) {
    _applyChipMeta(chipMeta);
    var msgs = _getActiveMsgs();
    var typing = document.getElementById(_getTypingId());
    if (!msgs) return;

    var bubble = document.createElement("div");
    bubble.className = "frai-bubble frai-agent";
    bubble.innerHTML = greet;
    _renderChips(chips, bubble);

    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(bubble, typing);
    } else {
        msgs.appendChild(bubble);
    }
    _scrollBottom();
}

// ════════════════════════════════════════════════════════════════
// ANALYZE WELCOME
// ════════════════════════════════════════════════════════════════
function _showAdvisorWelcome() {
    _fetchSuggestions("advisor", function (data) {
        var greet = data.greet || "Ask me anything about this page or document:";
        _renderWelcomeBubble(greet, data.chips || [], data.chip_meta);
    });
}


// ════════════════════════════════════════════════════════════════
// SEND MESSAGE (router)
// ════════════════════════════════════════════════════════════════
function sendMessage() {
    if (FRAI.sending) return;
    if (!_canSendMessage()) {
        _showApiSetupState();
        return;
    }
    if (FRAI.activeTab === "build" && FRAI.activeBuildSubtab !== "changes") {
        sendCodingMessage();
        return;
    }
    if (FRAI.activeTab === "advisor") { sendAdvisorMessage(); return; }
}

function _syncFormContext() {
    _resolveFormContext();
}

function _addContextHint(summary, evidence) {
    if (FRAI.activeTab !== "advisor") return;
    if (FRAI.config && FRAI.config.show_evidence === false) return;
    if (!summary && !(evidence && evidence.tools_used && evidence.tools_used.length)) return;

    var msgs = document.getElementById("frai-messages-advisor");
    if (!msgs) return;

    var hint = document.createElement("div");
    hint.className = "frai-context-hint";

    var parts = [];
    if (summary) {
        if (summary.indexOf("(") > -1 && summary.indexOf("Permission") === -1) {
            parts.push("Analyzed: " + summary);
        } else if (summary.indexOf("Report:") === 0) {
            parts.push(summary);
        } else if (summary === "Page context only" || summary === "Home dashboard") {
            parts.push("Page context — agent will fetch data via tools when needed");
        } else {
            parts.push(summary);
        }
    }

    if (evidence && evidence.tools_used && evidence.tools_used.length) {
        var toolLine = "Evidence: " + evidence.tools_used.map(function (t) {
            return (typeof t === "string") ? t : (t && t.name ? t.name : String(t));
        }).join(", ");
        if (evidence.checks_run > 0) {
            toolLine += " (" + evidence.checks_run + " issue" +
                (evidence.checks_run === 1 ? "" : "s") + " found)";
        }
        parts.push(toolLine);
    }

    hint.textContent = parts.join(" · ");

    var typing = document.getElementById("frai-typing-advisor");
    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(hint, typing);
    } else {
        msgs.appendChild(hint);
    }
    _scrollBottom();
}

function sendAdvisorMessage() {
    var input = document.getElementById("frai-input");
    if (!input) return;

    var text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    _syncFormContext();
    var analyzeMode = FRAI.analyzeMode || _resolveAnalyzeMode(text);
    var pageContext = _collectPageContext();
    var replyLocale = _detectReplyLocale(text);

    _addBubble(text, "frai-user");
    _showTyping();
    FRAI.sending = true;

    frappe.call({
        method: "frappe_pilot.api.analyze.chat",
        args: {
            message:      text,
            doctype:      FRAI.doctype      || "",
            docname:      FRAI.isNew ? "" : (FRAI.docname || ""),
            route:        FRAI.route        || "",
            list_doctype: FRAI.listDoctype  || pageContext.list_doctype || "",
            page_context: JSON.stringify(pageContext),
            mode:         analyzeMode,
            reply_locale: replyLocale,
        },
        callback: function (r) {
            FRAI.sending = false;
            FRAI.analyzeMode = "explain";
            _hideTyping();
            if (r && r.message) {
                if (r.message.needs_api_setup) {
                    _showApiSetupState();
                    return;
                }
                if (r.message.chip_meta) {
                    _applyChipMeta(r.message.chip_meta);
                }
                if (r.message.reply_locale) {
                    FRAI.replyLocale = r.message.reply_locale;
                }
                _addAdvisorBubble(
                    r.message.reply || "—",
                    r.message.chips,
                    r.message.nav_links,
                    r.message.navigation_action
                );
                _addContextHint(r.message.context_summary || "", r.message.evidence || null);
            } else {
                _addBubble("No response received.", "frai-error");
            }
        },
        error: function (err) {
            FRAI.sending = false;
            FRAI.analyzeMode = "explain";
            _hideTyping();
            _addBubble("Could not reach the server. Check that Frappe Pilot is installed.", "frai-error");
            console.error("[Frappe Pilot] advisor error:", err);
        }
    });
}

function _pilotNavigate(route) {
    if (!route || !route.length) return;
    frappe.set_route.apply(frappe, route);
    if (FRAI.config && FRAI.config.close_sidebar_on_navigate) {
        closePanel();
    }
}

function _renderNavLinks(container, navLinks) {
    if (!navLinks || !navLinks.length || !container) return;
    var wrap = document.createElement("div");
    wrap.className = "frai-nav-links";
    navLinks.forEach(function (link) {
        if (!link.route) return;
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "frai-nav-link";
        btn.textContent = link.button_label || link.label || "Open";
        btn.addEventListener("click", function () {
            _pilotNavigate(link.route);
        });
        wrap.appendChild(btn);
    });
    container.appendChild(wrap);
}

function _handleNavigationAction(container, action) {
    if (!action || !action.route) return;
    if (action.mode === "auto") {
        _pilotNavigate(action.route);
        return;
    }
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "frai-nav-confirm";
    btn.textContent = (_ui("nav_go_to") || "Go to {label}").replace("{label}", action.label || "page");
    btn.addEventListener("click", function () {
        _pilotNavigate(action.route);
    });
    container.appendChild(btn);
}

function _addAdvisorBubble(html, chips, navLinks, navigationAction) {
    _addBubble(html, "frai-agent", chips, navLinks, navigationAction);
}


// ════════════════════════════════════════════════════════════════
// DOM HELPERS
// ════════════════════════════════════════════════════════════════
function _getTypingId() {
    if (FRAI.activeTab === "build") return "frai-typing-coding";
    if (FRAI.activeTab === "advisor") return "frai-typing-advisor";
    return "frai-typing";
}

function _getTypingLabels() {
    if (FRAI.activeTab === "build") {
        var buildLabel = _ui("typing_build");
        return [buildLabel].concat(CODING_TYPING_LABELS.slice(1));
    }
    if (FRAI.activeTab === "advisor") {
        var advisorLabel = _ui("typing_advisor");
        return [advisorLabel].concat(ADVISOR_TYPING_LABELS.slice(1));
    }
    return GUIDE_TYPING_LABELS;
}

function _getActiveMsgs() {
    if (FRAI.activeTab === "build") {
        if (FRAI.activeBuildSubtab === "changes") return null;
        return document.getElementById("frai-messages-coding");
    }
    if (FRAI.activeTab === "advisor") {
        return document.getElementById("frai-messages-advisor");
    }
    return null;
}

function _addBubble(html, cssClass, chips, navLinks, navigationAction) {
    var msgs   = _getActiveMsgs();
    var typing = document.getElementById(_getTypingId());
    if (!msgs) return;

    var bubble = document.createElement("div");
    bubble.className = "frai-bubble " + (cssClass || "frai-agent");
    if (typeof html !== "string") {
        html = (html && html.message) ? String(html.message) : String(html || "—");
    }
    bubble.innerHTML = html;

    if (navigationAction && navigationAction.route) {
        if (navigationAction.mode !== "auto") {
            _handleNavigationAction(bubble, navigationAction);
        } else {
            _pilotNavigate(navigationAction.route);
        }
        var extraNavLinks = (navLinks || []).filter(function (link) {
            return link && link.route && !link.primary;
        });
        _renderNavLinks(bubble, extraNavLinks);
    } else {
        _renderNavLinks(bubble, navLinks);
    }

    if (chips && chips.length) {
        _renderChips(chips, bubble);
    }

    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(bubble, typing);
    } else {
        msgs.appendChild(bubble);
    }

    _scrollBottom();
}

function _removeAllChips() {
    document.querySelectorAll(".frai-chips").forEach(function (el) { el.remove(); });
}

function _removeCapGrid() {
    var grid = document.querySelector(".frai-cap-grid");
    if (grid) grid.remove();
}

function _showTyping() {
    var id = _getTypingId();
    var t  = document.getElementById(id);
    if (!t) return;
    t.classList.add("frai-visible");

    var labels  = _getTypingLabels();
    var labelEl = t.querySelector(".frai-typing-label");
    var idx = 0;
    if (labelEl) labelEl.textContent = labels[0];

    clearInterval(_typingLabelTimers[id]);
    _typingLabelTimers[id] = setInterval(function () {
        idx = (idx + 1) % labels.length;
        if (labelEl) labelEl.textContent = labels[idx];
    }, 1500);

    _scrollBottom();
}

function _hideTyping() {
    var id = _getTypingId();
    var t  = document.getElementById(id);
    if (t) t.classList.remove("frai-visible");
    clearInterval(_typingLabelTimers[id]);
    var labelEl = t && t.querySelector(".frai-typing-label");
    if (labelEl) labelEl.textContent = "Thinking…";
}

function _scrollBottom() {
    var msgs = _getActiveMsgs();
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}


// ════════════════════════════════════════════════════════════════
// CODING — welcome with capability grid
// ════════════════════════════════════════════════════════════════
function _showCodingWelcome() {
    _fetchSuggestions("build", function (data) {
        var greet = data.greet ||
            "I'm <strong>Frappe Pilot</strong> — I make real changes to ERPNext from plain English.<br>" +
            "Every change goes through a <strong>Review &rarr; Confirm</strong> step before it's applied.<br><br>" +
            "What do you want to build?";

        _addBubble(greet, "frai-agent");

        var msgs   = document.getElementById("frai-messages-coding");
        var typing = document.getElementById("frai-typing-coding");
        if (!msgs) return;

        var grid = _buildCapGrid(data.actions || []);
        if (typing && msgs.contains(typing)) {
            msgs.insertBefore(grid, typing);
        } else {
            msgs.appendChild(grid);
        }
        _scrollBottom();
    });
}

function _buildCapGrid(actions) {
    var caps = actions && actions.length ? actions : _fallbackSuggestions("build").actions;
    caps = _filterItemsByChipScope(caps);

    var grid = document.createElement("div");
    grid.className = "frai-cap-grid";

    caps.forEach(function (cap) {
        var card = document.createElement("div");
        card.className = "frai-cap-card";
        if (_isRtlLocale(cap.locale)) {
            card.setAttribute("dir", "rtl");
            card.setAttribute("lang", cap.locale);
        }
        card.innerHTML =
            '<span class="frai-cap-icon">' + (cap.icon || "⚙️") + '</span>' +
            '<span class="frai-cap-label">' + (cap.label || "") + '</span>' +
            '<span class="frai-cap-desc">' + (cap.desc || "") + '</span>';
        card.addEventListener("click", function () {
            var inputEl = document.getElementById("frai-input");
            if (inputEl) {
                inputEl.value = cap.prompt || "";
                FRAI.replyLocale = cap.locale || "en";
                inputEl.focus();
                inputEl.style.height = "auto";
                inputEl.style.height = Math.min(inputEl.scrollHeight, 96) + "px";
            }
        });
        grid.appendChild(card);
    });

    return grid;
}


// ════════════════════════════════════════════════════════════════
// CODING — send message with conversation history
// ════════════════════════════════════════════════════════════════
function sendCodingMessage() {
    var input = document.getElementById("frai-input");
    if (!input) return;

    var text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    _removeAllChips();
    _removeCapGrid();
    _addBubble(text, "frai-user");
    _showTyping();
    FRAI.sending = true;

    // Snapshot history before this turn (excludes current message)
    var historySnapshot = JSON.stringify(FRAI.codingHistory.slice(-14));

    // Optimistically add user message to history
    FRAI.codingHistory.push({ role: "user", content: text });

    frappe.call({
        method: "frappe_pilot.api.coding_agent.chat",
        args: {
            message: text,
            history: historySnapshot,
            doctype: FRAI.doctype || "",
            docname: FRAI.docname || "",
        },
        callback: function (r) {
            FRAI.sending = false;
            _hideTyping();
            if (!r || !r.message) {
                _addBubble("No response received.", "frai-error");
                return;
            }
            var data = r.message;
            if (data.needs_api_setup) {
                FRAI.codingHistory.pop();
                _showApiSetupState();
                return;
            }
            var replyText = data.reply || "";
            if (data.preview) {
                _showPreviewCard(replyText, data.preview);
                FRAI.codingHistory.push({ role: "assistant", content: data.preview.summary || replyText });
            } else {
                _addBubble(replyText || "—", "frai-agent");
                FRAI.codingHistory.push({ role: "assistant", content: replyText });
            }
        },
        error: function (err) {
            FRAI.sending = false;
            _hideTyping();
            FRAI.codingHistory.pop(); // remove the optimistic user message
            _addBubble(
                "Server error. Check that <code>groq_api_key</code> is set in site_config.json.",
                "frai-error"
            );
            console.error("[Frappe Pilot] build error:", err);
        },
    });
}


// ════════════════════════════════════════════════════════════════
// CODING — preview card (amber stripe + tool badge)
// ════════════════════════════════════════════════════════════════
function _showPreviewCard(previewHtml, preview) {
    var msgs = document.getElementById("frai-messages-coding");
    if (!msgs) return;

    FRAI.pendingSessionKey = preview.session_key;

    var toolLabel = TOOL_LABELS[preview.tool] || (preview.tool || "CHANGE").toUpperCase();

    var card = document.createElement("div");
    card.className = "frai-preview-card";

    var badge = document.createElement("div");
    badge.className = "frai-preview-badge";
    badge.textContent = toolLabel;

    var body = document.createElement("div");
    body.className = "frai-preview-body";
    body.innerHTML = previewHtml;

    var actions = document.createElement("div");
    actions.className = "frai-preview-actions";

    var applyBtn = document.createElement("button");
    applyBtn.className   = "frai-btn-apply";
    applyBtn.textContent = "Apply Changes";

    var cancelBtn = document.createElement("button");
    cancelBtn.className   = "frai-btn-cancel";
    cancelBtn.textContent = "Cancel";

    actions.appendChild(applyBtn);
    actions.appendChild(cancelBtn);
    card.appendChild(badge);
    card.appendChild(body);
    card.appendChild(actions);

    var typing = document.getElementById("frai-typing-coding");
    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(card, typing);
    } else {
        msgs.appendChild(card);
    }
    msgs.scrollTop = msgs.scrollHeight;

    applyBtn.addEventListener("click", function () {
        applyBtn.disabled    = true;
        cancelBtn.disabled   = true;
        applyBtn.textContent = "Applying…";
        _applyCodingChange(preview.session_key, card, preview.tool);
    });

    cancelBtn.addEventListener("click", function () {
        card.remove();
        FRAI.pendingSessionKey = null;
        _addBubble("Change cancelled.", "frai-agent");
    });
}

function _applyCodingChange(sessionKey, previewCard, toolName) {
    frappe.call({
        method: "frappe_pilot.api.coding_agent.apply",
        args:   { session_key: sessionKey },
        callback: function (r) {
            if (previewCard) previewCard.remove();
            FRAI.pendingSessionKey = null;

            if (!r || !r.message) {
                _addBubble("Apply failed — no response from server.", "frai-error");
                return;
            }
            var data = r.message;
            if (data.success) {
                _showSuccessCard(data.result, data.change_log, toolName);
            } else {
                _addBubble("Apply failed: " + (data.error || "unknown error"), "frai-error");
            }
        },
        error: function () {
            if (previewCard) previewCard.remove();
            FRAI.pendingSessionKey = null;
            _addBubble("Apply failed — server error.", "frai-error");
        },
    });
}


// ════════════════════════════════════════════════════════════════
// CODING — success card (green stripe + checkmark animation + suggestion)
// ════════════════════════════════════════════════════════════════
function _showSuccessCard(result, changeLogName, toolName) {
    var msgs = document.getElementById("frai-messages-coding");
    if (!msgs) return;

    var card = document.createElement("div");
    card.className = "frai-success-card";

    // Animated checkmark header
    var header = document.createElement("div");
    header.className = "frai-success-header";
    header.innerHTML =
        '<div class="frai-check-circle">' +
            '<svg class="frai-check-svg" viewBox="0 0 14 14">' +
                '<polyline class="frai-check-path" points="2,7 5.5,10.5 12,3"/>' +
            '</svg>' +
        '</div>' +
        '<span class="frai-success-title">Applied successfully</span>';

    var detail = document.createElement("div");
    detail.className = "frai-success-detail";
    var detailParts = [];
    if (result.doctype) detailParts.push(result.doctype);
    if (result.name || result.label) detailParts.push("<strong>" + (result.name || result.label) + "</strong>");
    if (result.target)               detailParts.push("on <em>" + result.target + "</em>");
    detail.innerHTML = detailParts.join(": ").replace(/: on/, " on");

    card.appendChild(header);
    card.appendChild(detail);

    // Smart suggestion pill
    var suggestion = toolName ? POST_APPLY_SUGGESTIONS[toolName] : null;
    if (suggestion) {
        var pill = document.createElement("button");
        pill.className   = "frai-suggestion-pill";
        pill.textContent = "💡 " + suggestion;
        pill.addEventListener("click", function () {
            pill.remove();
            var inputEl = document.getElementById("frai-input");
            if (inputEl) {
                inputEl.value = suggestion;
                inputEl.focus();
            }
        });
        card.appendChild(pill);
    }

    // Actions row
    var actionsDiv = document.createElement("div");
    actionsDiv.className = "frai-success-actions";

    var reloadBtn = document.createElement("button");
    reloadBtn.className   = "frai-btn-reload";
    reloadBtn.textContent = "↻ Reload page";
    reloadBtn.addEventListener("click", function () { window.location.reload(); });
    actionsDiv.appendChild(reloadBtn);

    if (changeLogName) {
        var undoBtn = document.createElement("button");
        undoBtn.className   = "frai-btn-undo";
        undoBtn.textContent = "↩ Undo";
        actionsDiv.appendChild(undoBtn);

        var errText = document.createElement("div");
        errText.style.cssText = "font-size:11px;color:var(--red,#e74c3c);margin-top:4px;display:none;";

        undoBtn.addEventListener("click", function () {
            undoBtn.disabled    = true;
            undoBtn.textContent = "Undoing…";
            errText.style.display = "none";

            frappe.call({
                method: "frappe_pilot.api.coding_agent.rollback",
                args:   { change_log_name: changeLogName },
                callback: function (r) {
                    var data = r && r.message;
                    if (data && data.success) {
                        card.remove();
                        _addBubble("↩ Change has been undone.", "frai-agent");
                    } else {
                        undoBtn.disabled    = false;
                        undoBtn.textContent = "↩ Undo";
                        errText.textContent   = (data && data.error) || "Rollback failed.";
                        errText.style.display = "block";
                    }
                },
                error: function () {
                    undoBtn.disabled    = false;
                    undoBtn.textContent = "↩ Undo";
                    errText.textContent   = "Server error — rollback failed.";
                    errText.style.display = "block";
                },
            });
        });

        card.appendChild(actionsDiv);
        card.appendChild(errText);
    } else {
        card.appendChild(actionsDiv);
    }

    var typing = document.getElementById("frai-typing-coding");
    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(card, typing);
    } else {
        msgs.appendChild(card);
    }
    msgs.scrollTop = msgs.scrollHeight;
}


// ════════════════════════════════════════════════════════════════
// HISTORY TAB
// ════════════════════════════════════════════════════════════════
function _loadHistory() {
    var listEl = document.getElementById("frai-history-list");
    if (!listEl) return;

    listEl.innerHTML = '<div class="frai-history-loading">Loading changes…</div>';

    frappe.call({
        method: "frappe_pilot.api.coding_agent.get_change_log",
        args:   { limit: 20 },
        callback: function (r) {
            var items = r && r.message;
            listEl.innerHTML = "";

            if (!items || !items.length) {
                listEl.innerHTML =
                    '<div class="frai-history-empty">' +
                        '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" ' +
                             'stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">' +
                            '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2"/>' +
                            '<rect x="9" y="3" width="6" height="4" rx="1"/>' +
                            '<line x1="9" y1="12" x2="15" y2="12"/>' +
                            '<line x1="9" y1="16" x2="13" y2="16"/>' +
                        '</svg>' +
                        'No changes yet.<br>Use the Build tab to make your first change.' +
                    '</div>';
                return;
            }

            items.forEach(function (item) {
                listEl.appendChild(_buildHistoryItem(item));
            });
        },
        error: function () {
            listEl.innerHTML = '<div class="frai-history-empty">Could not load history.</div>';
        }
    });
}

function _buildHistoryItem(item) {
    var badgeInfo  = HISTORY_BADGE_MAP[item.change_type] || { cls: "frai-hb-documents", label: item.change_type };
    var rolledBack = item.status === "Rolled Back";

    var div = document.createElement("div");
    div.className = "frai-history-item" + (rolledBack ? " frai-rolled-back" : "");

    var badge = document.createElement("span");
    badge.className = "frai-history-badge " + badgeInfo.cls;
    badge.textContent = badgeInfo.label;

    var info = document.createElement("div");
    info.className = "frai-history-info";

    var name = document.createElement("div");
    name.className = "frai-history-name";
    name.title     = item.change_name || "";
    name.textContent = item.change_name || "(unnamed)";

    var meta = document.createElement("div");
    meta.className = "frai-history-meta";
    var parts = [];
    if (item.target_doctype) parts.push(item.target_doctype);
    if (item.applied_at)     parts.push(_formatRelative(item.applied_at));
    meta.textContent = parts.join(" · ");

    info.appendChild(name);
    info.appendChild(meta);
    div.appendChild(badge);
    div.appendChild(info);

    if (rolledBack) {
        var label = document.createElement("span");
        label.className   = "frai-history-rolled-label";
        label.textContent = "Rolled back";
        div.appendChild(label);
    } else {
        var undoBtn = document.createElement("button");
        undoBtn.className   = "frai-history-undo-btn";
        undoBtn.textContent = "↩ Undo";
        undoBtn.addEventListener("click", function () {
            _rollbackHistoryItem(item.name, undoBtn, div);
        });
        div.appendChild(undoBtn);
    }

    return div;
}

function _rollbackHistoryItem(changeLogName, btn, row) {
    btn.disabled    = true;
    btn.textContent = "Undoing…";

    frappe.call({
        method: "frappe_pilot.api.coding_agent.rollback",
        args:   { change_log_name: changeLogName },
        callback: function (r) {
            var data = r && r.message;
            if (data && data.success) {
                btn.remove();
                var label = document.createElement("span");
                label.className   = "frai-history-rolled-label";
                label.textContent = "Rolled back";
                row.appendChild(label);
                row.classList.add("frai-rolled-back");
            } else {
                btn.disabled    = false;
                btn.textContent = "↩ Undo";
                frappe.show_alert({ message: (data && data.error) || "Rollback failed.", indicator: "red" });
            }
        },
        error: function () {
            btn.disabled    = false;
            btn.textContent = "↩ Undo";
            frappe.show_alert({ message: "Server error — rollback failed.", indicator: "red" });
        }
    });
}

function _formatRelative(dateStr) {
    if (!dateStr) return "";
    try {
        var d    = new Date(dateStr.replace(" ", "T"));
        var diff = (Date.now() - d.getTime()) / 1000;
        if (diff < 60)    return "just now";
        if (diff < 3600)  return Math.round(diff / 60) + "m ago";
        if (diff < 86400) return Math.round(diff / 3600) + "h ago";
        return Math.round(diff / 86400) + "d ago";
    } catch (e) {
        return dateStr;
    }
}
