// ============================================================
// ai_sidebar.js — Forge AI Assistant
// ============================================================

var FRAI = {
    isOpen:            false,
    activeTab:         "guide",
    doctype:           null,
    docname:           null,
    isNew:             false,
    route:             "",
    listDoctype:       null,
    sending:           false,
    panelWidth:        360,
    isResizing:        false,
    pendingSessionKey: null,
    codingHistory:     [],
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

var CODING_TYPING_LABELS = ["Thinking…", "Reading schema…", "Preparing change…", "Validating…"];
var GUIDE_TYPING_LABELS  = ["Thinking…", "Searching docs…", "Preparing answer…"];

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
    _injectCSS();
    _buildDOM();
    _bindEvents();
    _bindResizeEvents();
    _scheduleContextCheck();
});


// ════════════════════════════════════════════════════════════════
// CSS
// ════════════════════════════════════════════════════════════════
function _injectCSS() {
    var style = document.createElement("style");
    style.id = "frai-styles";
    style.textContent = `

/* ── Trigger (right-edge tab, Frappe-native) ── */
#frai-trigger {
    position: fixed;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    z-index: 1050;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 8px 10px 10px;
    background: var(--fg-color, #fff);
    border: 1px solid var(--border-color, #d1d8dd);
    border-right: none;
    border-radius: 8px 0 0 8px;
    cursor: pointer;
    box-shadow: -2px 0 8px rgba(0,0,0,.06);
    transition: padding .16s ease, box-shadow .16s ease, right .2s cubic-bezier(.4,0,.2,1);
    user-select: none;
}
#frai-trigger:hover {
    padding-left: 14px;
    box-shadow: -3px 0 12px rgba(0,0,0,.09);
}
#frai-trigger.frai-resizing { transition: none !important; }
#frai-trigger-dot {
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: #2490ef;
    flex-shrink: 0;
}
#frai-trigger-label {
    font-size: 11px;
    font-weight: 600;
    letter-spacing: .04em;
    color: var(--text-color, #36414c);
    writing-mode: vertical-rl;
    text-orientation: mixed;
    transform: rotate(180deg);
    white-space: nowrap;
}

/* ── Resize handle ── */
#frai-resize-handle {
    position: absolute;
    left: 0; top: 0;
    width: 5px; height: 100%;
    cursor: ew-resize;
    z-index: 10;
    background: transparent;
    transition: background .15s;
}
#frai-resize-handle:hover,
#frai-resize-handle.frai-dragging {
    background: var(--primary, #2490ef);
    opacity: .25;
}

/* ── Panel ── */
#frai-panel {
    position: fixed;
    top: 0; right: 0;
    height: 100dvh;
    width: 360px;
    min-width: 280px;
    max-width: 640px;
    z-index: 1049;
    display: flex;
    flex-direction: column;
    background: var(--fg-color, #fff);
    border-left: 1px solid var(--border-color, #d1d8dd);
    box-shadow: -4px 0 20px rgba(0,0,0,.07);
    transform: translateX(100%);
    transition: transform .22s cubic-bezier(.4,0,.2,1);
    overflow: hidden;
}
#frai-panel.frai-open     { transform: translateX(0); }
#frai-panel.frai-resizing { transition: none; }

/* ── Header (light, Frappe-native) ── */
#frai-header {
    flex-shrink: 0;
    padding: 12px 14px 0;
    background: var(--fg-color, #fff);
    border-bottom: 1px solid var(--border-color, #d1d8dd);
}
#frai-header-row {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 10px;
}
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
#frai-version {
    display: inline-block;
    font-size: 9px;
    font-weight: 500;
    color: var(--text-muted, #8d99a6);
    background: var(--control-bg, #f4f5f6);
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 4px;
    padding: 1px 5px;
    margin-left: 5px;
    vertical-align: middle;
    letter-spacing: 0.03em;
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

/* ── Chips (guide tab) ── */
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
#frai-typing-coding {
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
#frai-typing-coding.frai-visible { display: flex; }
#frai-typing i,
#frai-typing-coding i {
    display: inline-block;
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--text-muted, #8d99a6);
    animation: frai-dot .9s infinite;
    flex-shrink: 0;
}
#frai-typing i:nth-child(2),
#frai-typing-coding i:nth-child(2) { animation-delay: .15s; }
#frai-typing i:nth-child(3),
#frai-typing-coding i:nth-child(3) { animation-delay: .3s; }
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
    `;
    document.head.appendChild(style);
}


// ════════════════════════════════════════════════════════════════
// DOM
// ════════════════════════════════════════════════════════════════
function _buildDOM() {

    var trigger = document.createElement("div");
    trigger.id = "frai-trigger";
    trigger.setAttribute("title", "Open Forge AI (Alt+A)");
    trigger.innerHTML =
        '<div id="frai-trigger-dot"></div>' +
        '<span id="frai-trigger-label">Forge</span>';
    document.body.appendChild(trigger);

    var panel = document.createElement("div");
    panel.id = "frai-panel";
    panel.setAttribute("role", "complementary");
    panel.setAttribute("aria-label", "Forge AI Assistant");
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
                    '<div id="frai-title">Forge <span id="frai-version">v1.0</span></div>' +
                    '<div id="frai-subtitle">Loading…</div>' +
                '</div>' +
                '<button id="frai-close" aria-label="Close">&#10005;</button>' +
            '</div>' +
            '<div id="frai-tabs">' +
                '<button class="frai-tab frai-tab-active" data-tab="guide">Guide</button>' +
                '<button class="frai-tab" data-tab="coding">Build</button>' +
                '<button class="frai-tab" data-tab="history">History</button>' +
            '</div>' +
        '</div>' +

        '<div id="frai-body">' +

            '<div id="frai-pane-guide" class="frai-tab-pane frai-pane-active">' +
                '<div id="frai-messages-guide" class="frai-messages-area">' +
                    '<div id="frai-typing"><i></i><i></i><i></i>' +
                        '<span class="frai-typing-label">Thinking…</span>' +
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
                'placeholder="Ask anything about ERPNext…" ' +
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

        var startX     = e.clientX;
        var startWidth = panel.offsetWidth;

        function onMouseMove(e) {
            if (!FRAI.isResizing) return;
            var newWidth = Math.min(640, Math.max(280, startWidth + (startX - e.clientX)));
            FRAI.panelWidth = newWidth;
            panel.style.width   = newWidth + "px";
            trigger.style.right = newWidth + "px";
        }
        function onMouseUp() {
            FRAI.isResizing = false;
            panel.classList.remove("frai-resizing");
            trigger.classList.remove("frai-resizing");
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

    if (triggerEl) triggerEl.addEventListener("click", togglePanel);
    if (closeEl)   closeEl.addEventListener("click", closePanel);
    if (sendEl)    sendEl.addEventListener("click", sendMessage);

    document.querySelectorAll(".frai-tab").forEach(function (btn) {
        btn.addEventListener("click", function () { switchTab(btn.dataset.tab); });
    });

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

    document.addEventListener("keydown", function (e) {
        if (e.altKey && e.key === "a") togglePanel();
    });

    if (frappe.router) {
        frappe.router.on("change", function () {
            setTimeout(_updateContext, 400);
        });
    }

    $(document).on("form-refresh form-load", function () {
        setTimeout(_updateContext, 200);
    });
}

function _scheduleContextCheck() {
    setTimeout(_updateContext, 600);
    setTimeout(_updateContext, 1500);
}


// ════════════════════════════════════════════════════════════════
// PANEL OPEN / CLOSE
// ════════════════════════════════════════════════════════════════
function togglePanel() { FRAI.isOpen ? closePanel() : openPanel(); }

function openPanel() {
    FRAI.isOpen = true;
    var panel   = document.getElementById("frai-panel");
    var trigger = document.getElementById("frai-trigger");
    if (!panel) return;

    panel.style.width = FRAI.panelWidth + "px";
    panel.classList.add("frai-open");
    if (trigger) trigger.style.right = FRAI.panelWidth + "px";

    var guideMsgs = document.getElementById("frai-messages-guide");
    if (guideMsgs && guideMsgs.querySelectorAll(".frai-bubble").length === 0) {
        _showWelcome();
    }

    var inputEl = document.getElementById("frai-input");
    if (inputEl) inputEl.focus();
}

function closePanel() {
    FRAI.isOpen = false;
    var panel   = document.getElementById("frai-panel");
    var trigger = document.getElementById("frai-trigger");
    if (panel)   panel.classList.remove("frai-open");
    if (trigger) trigger.style.right = "0";
}


// ════════════════════════════════════════════════════════════════
// TAB SWITCHING
// ════════════════════════════════════════════════════════════════
function switchTab(tab) {
    FRAI.activeTab = tab;

    document.querySelectorAll(".frai-tab").forEach(function (b) {
        b.classList.toggle("frai-tab-active", b.dataset.tab === tab);
    });
    document.querySelectorAll(".frai-tab-pane").forEach(function (p) {
        p.classList.remove("frai-pane-active");
    });
    var activePane = document.getElementById("frai-pane-" + tab);
    if (activePane) activePane.classList.add("frai-pane-active");

    var footer = document.getElementById("frai-footer");
    var input  = document.getElementById("frai-input");
    var sendEl = document.getElementById("frai-send");

    if (tab === "history") {
        if (footer) footer.style.display = "none";
        _loadHistory();
        return;
    }

    if (footer) footer.style.display = "flex";

    if (tab === "guide") {
        if (input)  { input.placeholder = "Ask anything about ERPNext…"; input.disabled = false; }
        if (sendEl) sendEl.disabled = false;
        var guideMsgs = document.getElementById("frai-messages-guide");
        if (guideMsgs && guideMsgs.querySelectorAll(".frai-bubble").length === 0) {
            _showWelcome();
        }

    } else if (tab === "coding") {
        if (input)  { input.placeholder = "Tell me what to build or change in ERPNext…"; input.disabled = false; }
        if (sendEl) sendEl.disabled = false;
        var codingMsgs = document.getElementById("frai-messages-coding");
        if (codingMsgs && codingMsgs.querySelectorAll(".frai-bubble, .frai-preview-card, .frai-success-card").length === 0) {
            _showCodingWelcome();
        }
    }
}


// ════════════════════════════════════════════════════════════════
// CONTEXT DETECTION
// ════════════════════════════════════════════════════════════════
function _updateContext() {
    var subtitle = document.getElementById("frai-subtitle");
    if (!subtitle) return;

    if (frappe.cur_frm) {
        FRAI.doctype     = frappe.cur_frm.doctype;
        FRAI.docname     = frappe.cur_frm.docname;
        FRAI.isNew       = frappe.cur_frm.is_new();
        FRAI.route       = "";
        FRAI.listDoctype = null;

        subtitle.textContent = FRAI.doctype + ": " + (FRAI.isNew ? "(New)" : FRAI.docname);

        if (FRAI.isOpen && FRAI.activeTab === "guide") {
            var guideMsgs = document.getElementById("frai-messages-guide");
            if (guideMsgs && guideMsgs.querySelectorAll(".frai-bubble").length === 0) {
                _showWelcome();
            }
        }

    } else {
        FRAI.doctype = null;
        FRAI.docname = null;
        FRAI.isNew   = false;

        var routeArr = [];
        if (frappe.get_route) {
            try { routeArr = frappe.get_route() || []; } catch(e) { routeArr = []; }
        }

        if (routeArr.length >= 2 && routeArr[0] === "List") {
            FRAI.listDoctype = routeArr[1];
        } else {
            FRAI.listDoctype = null;
        }

        var route = routeArr.length ? routeArr.join(" > ") : "";
        if (!route && frappe.get_route_str) {
            try { route = frappe.get_route_str() || ""; } catch(e) {}
        }
        if (!route) {
            route = (window.location.hash || "").replace(/^#\/?/, "") || "Home";
        }

        FRAI.route = route;
        subtitle.textContent = _buildSubtitleLabel(routeArr, route);
    }
}

function _buildSubtitleLabel(routeArr, route) {
    if (!routeArr.length && !route) return "Home";
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
// GUIDE WELCOME
// ════════════════════════════════════════════════════════════════
function _showWelcome() {
    var chips = _getContextChips();
    var greet;

    if (FRAI.doctype) {
        greet = "I can see you're on the <strong>" + FRAI.doctype + "</strong> form. " +
                "Here are some things I can help you with:";
    } else if (FRAI.listDoctype) {
        greet = "I can see you're on the <strong>" + FRAI.listDoctype + " list</strong>. " +
                "Here are some things I can help you with:";
    } else if (FRAI.route) {
        var routeArr = [];
        try { routeArr = frappe.get_route ? (frappe.get_route() || []) : []; } catch(e) {}
        greet = "I can see you're on the <strong>" +
                _buildSubtitleLabel(routeArr, FRAI.route) +
                "</strong> page. Here are some things I can help you with:";
    } else {
        greet = "Hi! I'm your ERPNext Guide. Pick a question below or ask anything:";
    }

    _addBubble(greet, "frai-agent", chips);
}

function _getContextChips() {
    var formMap = {
        "Customer":         ["How do I add a GSTIN field?", "How do I set a credit limit?", "How do I link contacts?", "How do I create a Sales Order?"],
        "Supplier":         ["How do I track outstanding payments?", "How do I set payment terms?", "How do I add a PAN field?", "How do I block a supplier?"],
        "Sales Invoice":    ["What happens when I submit this?", "How do I apply a discount?", "How do I create a credit note?", "How do I record a partial payment?"],
        "Purchase Invoice": ["How do I match this to a PO?", "How do I record a partial payment?", "What is Save vs Submit?", "How do I handle a debit note?"],
        "Sales Order":      ["How do I create an invoice from this?", "How do I check delivery status?", "How do I add an approval workflow?", "How do I handle partial delivery?"],
        "Purchase Order":   ["How do I receive goods against this?", "How do I set up approval workflow?", "How do I create a Purchase Invoice?", "How do I cancel and amend?"],
        "Employee":         ["How do I set up payroll?", "How do I assign a leave policy?", "How do I add an emergency contact?", "How do I track attendance?"],
        "Item":             ["How do I add item variants?", "How do I set a reorder level?", "How do I track in multiple warehouses?", "Stock vs non-stock items?"],
        "Payment Entry":    ["How do I reconcile against an invoice?", "How do I handle foreign currency?", "How do I reverse this payment?", "What accounts does this affect?"],
        "Stock Entry":      ["Material Transfer vs Issue?", "How do I do a stock reconciliation?", "How do I track batch numbers?", "How do I move stock between warehouses?"],
        "Delivery Note":    ["How do I create an invoice from this?", "How do I track the Sales Order?", "How do I handle a return?", "How do I print a packing slip?"],
        "Journal Entry":    ["When to use this vs Payment Entry?", "How do I reverse this entry?", "How do I reconcile with bank?", "Debit vs credit here?"],
        "Warehouse":        ["How do I transfer stock here?", "How do I check stock levels?", "How do I set a default warehouse?", "How do I create a child warehouse?"],
        "Lead":             ["How do I convert to a customer?", "How do I assign to a salesperson?", "How do I schedule a follow-up?", "How do I track lead source?"],
        "Quotation":        ["How do I convert to Sales Order?", "How do I apply a discount?", "How do I send by email?", "How do I set an expiry date?"],
        "Social Login Key": ["What is a Social Login Key?", "How do I set up Google login?", "How do I get a Client ID and Secret?", "How do I enable OAuth for ERPNext?"]
    };

    if (FRAI.doctype && formMap[FRAI.doctype]) return formMap[FRAI.doctype];

    var listMap = {
        "Customer":        ["How do I create a new customer?", "How do I filter by territory?", "How do I export this list?", "How do I bulk update?"],
        "Item":            ["How do I create a new item?", "How do I check stock levels?", "How do I set item prices?", "How do I add variants?"],
        "Sales Invoice":   ["How do I create a new invoice?", "How do I filter unpaid invoices?", "How do I see overdue invoices?", "How do I bulk send by email?"],
        "Purchase Order":  ["How do I create a PO?", "How do I check pending orders?", "How do I filter by supplier?", "How do I close a PO?"],
        "Stock Entry":     ["How do I create a stock transfer?", "How do I do a reconciliation?", "How do I filter by warehouse?", "What are the entry types?"],
        "Employee":        ["How do I add a new employee?", "How do I filter by department?", "How do I export employee data?", "How do I check attendance?"],
        "Payment Entry":   ["How do I record a payment?", "How do I reconcile payments?", "How do I filter unreconciled?", "How do I handle advances?"],
        "Supplier":        ["How do I add a supplier?", "How do I check outstanding payables?", "How do I filter by group?", "How do I block a supplier?"],
        "Social Login Key":["What is a Social Login Key?", "How do I add a new provider?", "How do I set up Google OAuth?", "How do I get a Client Secret?"]
    };

    if (FRAI.listDoctype && listMap[FRAI.listDoctype]) return listMap[FRAI.listDoctype];

    if (FRAI.route) {
        var r = FRAI.route.toLowerCase();
        if (r.includes("stock"))    return ["How do I do a stock transfer?", "How do I check stock levels?", "What is a Stock Entry?", "How do I set a reorder level?"];
        if (r.includes("selling"))  return ["How do I create a Sales Order?", "How do I apply a discount?", "How do I create a quotation?", "How do I track outstanding invoices?"];
        if (r.includes("buying"))   return ["How do I create a Purchase Order?", "How do I record goods received?", "How do I set payment terms?", "How do I create a Purchase Invoice?"];
        if (r.includes("account"))  return ["How do I reconcile a bank statement?", "How do I create a Journal Entry?", "How do I record a payment?", "How do I view the general ledger?"];
        if (r.includes("hr"))       return ["How do I run payroll?", "How do I mark attendance?", "How do I set up leave policies?", "How do I create an employee?"];
        if (r.includes("integrat")) return ["What is a Social Login Key?", "How do I set up OAuth?", "How do I connect to third-party apps?", "How do I use REST API?"];
        if (r.includes("report"))   return ["How do I filter this report?", "How do I export report data?", "How do I save filters?", "How do I schedule by email?"];
    }

    return [
        "What is a DocType?",
        "How do I add a custom field?",
        "How do workflows work?",
        "How do I set up permissions?"
    ];
}


// ════════════════════════════════════════════════════════════════
// SEND MESSAGE (router)
// ════════════════════════════════════════════════════════════════
function sendMessage() {
    if (FRAI.sending) return;
    if (FRAI.activeTab === "coding")  { sendCodingMessage(); return; }
    if (FRAI.activeTab !== "guide") return;

    var input = document.getElementById("frai-input");
    if (!input) return;

    var text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    _addBubble(text, "frai-user");
    _showTyping();
    FRAI.sending = true;

    if (frappe.cur_frm) {
        FRAI.doctype     = frappe.cur_frm.doctype;
        FRAI.docname     = frappe.cur_frm.docname;
        FRAI.listDoctype = null;
        FRAI.route       = "";
    }

    frappe.call({
        method: "frappe_ai_assistant.api.guide.chat",
        args: {
            message:      text,
            doctype:      FRAI.doctype      || "",
            docname:      FRAI.docname      || "",
            route:        FRAI.route        || "",
            list_doctype: FRAI.listDoctype  || "",
            mode:         "guide"
        },
        callback: function (r) {
            FRAI.sending = false;
            _hideTyping();
            if (r && r.message) {
                _addBubble(r.message.reply || "—", "frai-agent");
            } else {
                _addBubble("No response received.", "frai-error");
            }
        },
        error: function (err) {
            FRAI.sending = false;
            _hideTyping();
            _addBubble(
                "Could not reach the server. Check that <code>groq_api_key</code> " +
                "is set in site_config.json and the app is installed.",
                "frai-error"
            );
            console.error("[Forge] guide error:", err);
        }
    });
}


// ════════════════════════════════════════════════════════════════
// DOM HELPERS
// ════════════════════════════════════════════════════════════════
function _getActiveMsgs() {
    var tab = FRAI.activeTab === "history" ? "guide" : FRAI.activeTab;
    return document.getElementById("frai-messages-" + tab);
}

function _addBubble(html, cssClass, chips) {
    var msgs   = _getActiveMsgs();
    var typingId = FRAI.activeTab === "coding" ? "frai-typing-coding" : "frai-typing";
    var typing = document.getElementById(typingId);
    if (!msgs) return;

    var bubble = document.createElement("div");
    bubble.className = "frai-bubble " + (cssClass || "frai-agent");
    bubble.innerHTML = html;

    if (chips && chips.length) {
        var wrap = document.createElement("div");
        wrap.className = "frai-chips";
        chips.forEach(function (text) {
            var chip = document.createElement("button");
            chip.className = "frai-chip";
            chip.textContent = text;
            chip.addEventListener("click", function () {
                var inputEl = document.getElementById("frai-input");
                if (inputEl) inputEl.value = text;
                _removeAllChips();
                sendMessage();
            });
            wrap.appendChild(chip);
        });
        bubble.appendChild(wrap);
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
    var id = FRAI.activeTab === "coding" ? "frai-typing-coding" : "frai-typing";
    var t  = document.getElementById(id);
    if (!t) return;
    t.classList.add("frai-visible");

    var labels  = FRAI.activeTab === "coding" ? CODING_TYPING_LABELS : GUIDE_TYPING_LABELS;
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
    var id = FRAI.activeTab === "coding" ? "frai-typing-coding" : "frai-typing";
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
    _addBubble(
        "I'm <strong>Forge</strong> — I make real changes to ERPNext from plain English.<br>" +
        "Every change goes through a <strong>Review &rarr; Confirm</strong> step before it's applied.<br><br>" +
        "What do you want to build?",
        "frai-agent"
    );

    var msgs   = document.getElementById("frai-messages-coding");
    var typing = document.getElementById("frai-typing-coding");
    if (!msgs) return;

    var grid = _buildCapGrid();
    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(grid, typing);
    } else {
        msgs.appendChild(grid);
    }
    _scrollBottom();
}

function _buildCapGrid() {
    var caps = [
        { icon: "⚙️", label: "Custom Fields", desc: "Add fields to any existing form",  prompt: "Add a custom field to " },
        { icon: "📄", label: "New DocType",    desc: "Create a new table from scratch",   prompt: "Create a new DocType called " },
        { icon: "⚡",  label: "Scripts",        desc: "Python and JS automation",          prompt: "Write a server script that " },
        { icon: "🔀", label: "Workflows",      desc: "Approval flows with roles",          prompt: "Create an approval workflow for " },
    ];

    var grid = document.createElement("div");
    grid.className = "frai-cap-grid";

    caps.forEach(function (cap) {
        var card = document.createElement("div");
        card.className = "frai-cap-card";
        card.innerHTML =
            '<span class="frai-cap-icon">' + cap.icon + '</span>' +
            '<span class="frai-cap-label">' + cap.label + '</span>' +
            '<span class="frai-cap-desc">' + cap.desc + '</span>';
        card.addEventListener("click", function () {
            var inputEl = document.getElementById("frai-input");
            if (inputEl) {
                inputEl.value = cap.prompt;
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
        method: "frappe_ai_assistant.api.coding_agent.chat",
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
            console.error("[Forge] build error:", err);
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
        method: "frappe_ai_assistant.api.coding_agent.apply",
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
                method: "frappe_ai_assistant.api.coding_agent.rollback",
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
        method: "frappe_ai_assistant.api.coding_agent.get_change_log",
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
        method: "frappe_ai_assistant.api.coding_agent.rollback",
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
