// ============================================================
// ai_sidebar.js
// Place at: frappe_ai_assistant/frappe_ai_assistant/public/js/ai_sidebar.js
// ============================================================

var FRAI = {
    isOpen:      false,
    activeTab:   "guide",
    doctype:     null,
    docname:     null,
    isNew:       false,
    route:       "",
    listDoctype: null,
    sending:     false,
    panelWidth:  340,
    isResizing:  false,
    pendingSessionKey: null,   // coding agent: staged change awaiting confirm
};

$(document).ready(function () {
    _injectCSS();
    _buildDOM();
    _bindEvents();
    _bindResizeEvents();
    _scheduleContextCheck();
    console.log("[Frappe AI] Sidebar ready.");
});


// ════════════════════════════════════════════════════════════════
// CSS
// ════════════════════════════════════════════════════════════════
function _injectCSS() {
    var style = document.createElement("style");
    style.id = "frai-styles";
    style.textContent = `

#frai-trigger {
    position: fixed;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    z-index: 1050;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 8px 10px 12px;
    background: var(--fg-color, #fff);
    border: 1px solid var(--border-color, #d1d8dd);
    border-right: none;
    border-radius: 8px 0 0 8px;
    cursor: pointer;
    box-shadow: -2px 0 8px rgba(0,0,0,.06);
    transition: padding .18s ease, box-shadow .18s ease, right .22s cubic-bezier(.4,0,.2,1);
    user-select: none;
}
#frai-trigger:hover {
    padding-left: 16px;
    box-shadow: -3px 0 14px rgba(0,0,0,.10);
}
#frai-trigger-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary, #2490ef);
    flex-shrink: 0;
    animation: frai-pulse 2.4s infinite;
}
@keyframes frai-pulse {
    0%,100% { opacity:1; transform:scale(1); }
    50%      { opacity:.5; transform:scale(.75); }
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

#frai-resize-handle {
    position: absolute;
    left: 0;
    top: 0;
    width: 5px;
    height: 100%;
    cursor: ew-resize;
    z-index: 10;
    background: transparent;
    transition: background .15s;
}
#frai-resize-handle:hover,
#frai-resize-handle.frai-dragging {
    background: var(--primary, #2490ef);
    opacity: .35;
}

#frai-panel {
    position: fixed;
    top: 0;
    right: 0;
    height: 100dvh;
    width: 340px;
    min-width: 260px;
    max-width: 600px;
    z-index: 1049;
    display: flex;
    flex-direction: column;
    background: var(--fg-color, #fff);
    border-left: 1px solid var(--border-color, #d1d8dd);
    box-shadow: -6px 0 24px rgba(0,0,0,.08);
    transform: translateX(100%);
    transition: transform .22s cubic-bezier(.4,0,.2,1);
    overflow: hidden;
}
#frai-panel.frai-open { transform: translateX(0); }
#frai-panel.frai-resizing { transition: none; }

#frai-header {
    flex-shrink: 0;
    padding: 14px 14px 0;
    background: var(--fg-color, #fff);
    border-bottom: 1px solid var(--border-color, #d1d8dd);
}
#frai-header-row {
    display: flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 10px;
}
#frai-icon-wrap {
    width: 30px;
    height: 30px;
    border-radius: 8px;
    background: var(--primary-light, #e8f3fd);
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
#frai-icon-wrap svg {
    width: 16px;
    height: 16px;
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
    width: 26px;
    height: 26px;
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
    transition: background .12s;
}
#frai-close:hover {
    background: var(--control-bg, #f4f5f6);
    color: var(--text-color, #36414c);
}

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
    border: 1px solid var(--red-highlight-color, #fbd5d5);
}
.frai-bubble.frai-disabled {
    align-self: flex-start;
    background: var(--yellow-highlight-color, #fffbe6);
    color: var(--text-color, #36414c);
    border: 1px solid var(--yellow-avatar-bg, #fde68a);
}

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
    background: var(--primary-light, #e8f3fd);
}

#frai-typing,
#frai-typing-coding {
    display: none;
    align-self: flex-start;
    gap: 5px;
    align-items: center;
    padding: 10px 14px;
    background: var(--control-bg, #f4f5f6);
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 4px 10px 10px 10px;
}
#frai-typing.frai-visible,
#frai-typing-coding.frai-visible { display: flex; }
#frai-typing span,
#frai-typing-coding span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--text-muted, #8d99a6);
    animation: frai-dot .9s infinite;
}
#frai-typing span:nth-child(2),
#frai-typing-coding span:nth-child(2) { animation-delay: .15s; }
#frai-typing span:nth-child(3),
#frai-typing-coding span:nth-child(3) { animation-delay: .3s; }
@keyframes frai-dot {
    0%,80%,100% { transform:scale(.7); opacity:.4; }
    40%          { transform:scale(1);  opacity:1; }
}

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
    width: 34px;
    height: 34px;
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
    width: 15px;
    height: 15px;
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

/* ── Coding Agent: preview card ── */
.frai-preview-card {
    align-self: flex-start;
    width: 94%;
    background: #f0f9ff;
    border: 1px solid #bae6fd;
    border-radius: 4px 10px 10px 10px;
    padding: 12px;
    font-size: 12px;
    line-height: 1.6;
    animation: frai-in .15s ease;
}
.frai-preview-card h4 {
    font-size: 11.5px;
    font-weight: 700;
    color: #0369a1;
    margin: 0 0 8px 0;
}
.frai-preview-body {
    color: var(--text-color, #36414c);
    margin-bottom: 10px;
}
.frai-preview-body ul {
    margin: 4px 0;
    padding-left: 16px;
}
.frai-preview-body pre {
    font-size: 10.5px;
    white-space: pre-wrap;
    background: #fff;
    padding: 6px 8px;
    border-radius: 4px;
    border: 1px solid #e2e8f0;
    margin: 4px 0;
    overflow-x: auto;
}
.frai-preview-actions {
    display: flex;
    gap: 6px;
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

/* ── Coding Agent: success card ── */
.frai-success-card {
    align-self: flex-start;
    width: 94%;
    background: #f0fdf4;
    border: 1px solid #bbf7d0;
    border-radius: 4px 10px 10px 10px;
    padding: 12px;
    font-size: 12px;
    line-height: 1.6;
    animation: frai-in .15s ease;
}
.frai-success-card h4 {
    font-size: 11.5px;
    font-weight: 700;
    color: #15803d;
    margin: 0 0 4px 0;
}
.frai-rollback-link {
    display: inline-block;
    margin-top: 6px;
    font-size: 11px;
    color: var(--text-muted, #8d99a6);
    text-decoration: underline;
    cursor: pointer;
    background: none;
    border: none;
    padding: 0;
}
.frai-rollback-link:hover { color: var(--red, #e74c3c); }
    `;
    document.head.appendChild(style);
}


// ════════════════════════════════════════════════════════════════
// DOM
// ════════════════════════════════════════════════════════════════
function _buildDOM() {

    var trigger = document.createElement("div");
    trigger.id = "frai-trigger";
    trigger.setAttribute("title", "Open AI Assistant (Alt+A)");
    trigger.innerHTML =
        '<div id="frai-trigger-dot"></div>' +
        '<span id="frai-trigger-label">AI</span>';
    document.body.appendChild(trigger);

    var panel = document.createElement("div");
    panel.id = "frai-panel";
    panel.setAttribute("role", "complementary");
    panel.setAttribute("aria-label", "AI Assistant");
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
                    '<div id="frai-title">AI Assistant</div>' +
                    '<div id="frai-subtitle">Loading...</div>' +
                '</div>' +
                '<button id="frai-close" aria-label="Close">&#10005;</button>' +
            '</div>' +
            '<div id="frai-tabs">' +
                '<button class="frai-tab frai-tab-active" data-tab="guide">Guide</button>' +
                '<button class="frai-tab" data-tab="coding">Coding Agent</button>' +
            '</div>' +
        '</div>' +

        '<div id="frai-body">' +

            '<div id="frai-pane-guide" class="frai-tab-pane frai-pane-active">' +
                '<div id="frai-messages-guide" class="frai-messages-area">' +
                    '<div id="frai-typing"><span></span><span></span><span></span></div>' +
                '</div>' +
            '</div>' +

            '<div id="frai-pane-coding" class="frai-tab-pane">' +
                '<div id="frai-messages-coding" class="frai-messages-area">' +
                    '<div id="frai-typing-coding"><span></span><span></span><span></span></div>' +
                '</div>' +
            '</div>' +

        '</div>' +

        '<div id="frai-footer">' +
            '<textarea id="frai-input" rows="1" ' +
                'placeholder="Ask anything about ERPNext..." ' +
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
    var handle  = document.getElementById("frai-resize-handle");
    var panel   = document.getElementById("frai-panel");
    var trigger = document.getElementById("frai-trigger");
    if (!handle || !panel || !trigger) return;

    handle.addEventListener("mousedown", function (e) {
        e.preventDefault();
        FRAI.isResizing = true;
        panel.classList.add("frai-resizing");
        handle.classList.add("frai-dragging");
        document.body.classList.add("frai-is-resizing");

        var startX     = e.clientX;
        var startWidth = panel.offsetWidth;

        function onMouseMove(e) {
            if (!FRAI.isResizing) return;
            var newWidth = Math.min(600, Math.max(260, startWidth + (startX - e.clientX)));
            FRAI.panelWidth = newWidth;
            panel.style.width   = newWidth + "px";
            trigger.style.right = newWidth + "px";
        }
        function onMouseUp() {
            FRAI.isResizing = false;
            panel.classList.remove("frai-resizing");
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
    if (!panel || !trigger) return;

    panel.style.width = FRAI.panelWidth + "px";
    panel.classList.add("frai-open");
    trigger.style.right = FRAI.panelWidth + "px";

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
// TAB SWITCHING — each tab keeps its own history
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

    var input  = document.getElementById("frai-input");
    var sendEl = document.getElementById("frai-send");

    if (tab === "guide") {
        if (input)  { input.placeholder = "Ask anything about ERPNext..."; input.disabled = false; }
        if (sendEl) sendEl.disabled = false;
        var guideMsgs = document.getElementById("frai-messages-guide");
        if (guideMsgs && guideMsgs.querySelectorAll(".frai-bubble").length === 0) {
            _showWelcome();
        }

    } else if (tab === "coding") {
        if (input)  { input.placeholder = "Tell me what to add or change in ERPNext..."; input.disabled = false; }
        if (sendEl) sendEl.disabled = false;
        var codingMsgs = document.getElementById("frai-messages-coding");
        if (codingMsgs && codingMsgs.querySelectorAll(".frai-bubble, .frai-preview-card, .frai-success-card").length === 0) {
            _showCodingWelcome();
        }
    }
}


// ════════════════════════════════════════════════════════════════
// CONTEXT DETECTION — reads the live Frappe page accurately
// ════════════════════════════════════════════════════════════════
function _updateContext() {
    var subtitle = document.getElementById("frai-subtitle");
    if (!subtitle) return;

    if (frappe.cur_frm) {
        // ── On a document form ───────────────────────────────
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
        // ── On list, report, module page, dashboard ──────────
        FRAI.doctype = null;
        FRAI.docname = null;
        FRAI.isNew   = false;

        var routeArr = [];

        // frappe.get_route() is the most reliable — returns an array
        if (frappe.get_route) {
            try { routeArr = frappe.get_route() || []; } catch(e) { routeArr = []; }
        }

        // Extract listDoctype from list views: ["List", "Customer", "List"]
        if (routeArr.length >= 2 && routeArr[0] === "List") {
            FRAI.listDoctype = routeArr[1];
        } else {
            FRAI.listDoctype = null;
        }

        // Build route string
        var route = routeArr.length ? routeArr.join(" > ") : "";

        // Fallback to get_route_str
        if (!route && frappe.get_route_str) {
            try { route = frappe.get_route_str() || ""; } catch(e) {}
        }

        // Fallback to URL hash
        if (!route) {
            route = (window.location.hash || "").replace(/^#\/?/, "") || "Home";
        }

        FRAI.route = route;
        subtitle.textContent = _buildSubtitleLabel(routeArr, route);

        console.log("[Frappe AI] Context →", {
            routeArr:    routeArr,
            route:       route,
            listDoctype: FRAI.listDoctype
        });
    }
}

function _buildSubtitleLabel(routeArr, route) {
    if (!routeArr.length && !route) return "Home";

    // List view: ["List", "Customer", "List"] → "Customer List"
    if (routeArr[0] === "List" && routeArr[1]) return routeArr[1] + " List";

    // Reports
    if ((routeArr[0] === "query-report" || routeArr[0] === "Report") && routeArr[1]) {
        return "Report: " + routeArr[1];
    }

    // Module home (single item): ["Buying"] → "Buying Module"
    if (routeArr.length === 1) return routeArr[0] + " Module";

    // Dashboard / Workspace
    if (routeArr[0] === "dashboard" || routeArr[0] === "Dashboard") return "Dashboard";
    if (routeArr[0] === "Workspaces" || routeArr[0] === "workspace") {
        return routeArr[1] ? routeArr[1] + " Workspace" : "Workspace";
    }

    // Generic fallback
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
// WELCOME — context-aware opening message + chips
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
// SEND MESSAGE
// ════════════════════════════════════════════════════════════════
function sendMessage() {
    if (FRAI.sending) return;
    if (FRAI.activeTab === "coding") { sendCodingMessage(); return; }
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

    // Refresh context right before sending — most accurate snapshot
    if (frappe.cur_frm) {
        FRAI.doctype     = frappe.cur_frm.doctype;
        FRAI.docname     = frappe.cur_frm.docname;
        FRAI.listDoctype = null;
        FRAI.route       = "";
    }

    var sendDoctype  = FRAI.doctype      || "";
    var sendDocname  = FRAI.docname      || "";
    var sendListDoc  = FRAI.listDoctype  || "";
    var sendRoute    = FRAI.route        || "";

    console.log("[Frappe AI] Sending →", {
        doctype:      sendDoctype,
        docname:      sendDocname,
        list_doctype: sendListDoc,
        route:        sendRoute,
        message:      text
    });

    frappe.call({
        method: "frappe_ai_assistant.api.guide.chat",
        args: {
            message:      text,
            doctype:      sendDoctype,
            docname:      sendDocname,
            route:        sendRoute,
            list_doctype: sendListDoc,
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
            console.error("[Frappe AI] error:", err);
        }
    });
}


// ════════════════════════════════════════════════════════════════
// DOM HELPERS
// ════════════════════════════════════════════════════════════════

function _getActiveMsgs() {
    return document.getElementById("frai-messages-" + FRAI.activeTab);
}

function _addBubble(html, cssClass, chips) {
    var msgs   = _getActiveMsgs();
    var typing = FRAI.activeTab === "coding"
        ? document.getElementById("frai-typing-coding")
        : document.getElementById("frai-typing");
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

function _showTyping() {
    var id = FRAI.activeTab === "coding" ? "frai-typing-coding" : "frai-typing";
    var t  = document.getElementById(id);
    if (t) t.classList.add("frai-visible");
    _scrollBottom();
}

function _hideTyping() {
    var id = FRAI.activeTab === "coding" ? "frai-typing-coding" : "frai-typing";
    var t  = document.getElementById(id);
    if (t) t.classList.remove("frai-visible");
}

function _scrollBottom() {
    var msgs = _getActiveMsgs();
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}


// ════════════════════════════════════════════════════════════════
// CODING AGENT
// ════════════════════════════════════════════════════════════════

function _showCodingWelcome() {
    var chips = [
        "Add a GSTIN field to Customer",
        "Add a 'Priority' select field to Sales Order",
        "Create a workflow for Purchase Order approval",
        "Validate that email is filled on Customer save",
    ];
    _addBubble(
        "I'm the <strong>Coding Agent</strong>. I can make real changes to your ERPNext — " +
        "adding custom fields, writing server/client scripts, or building approval workflows.<br><br>" +
        "Every change goes through a <strong>Review &rarr; Confirm</strong> step before anything is applied.",
        "frai-agent",
        chips
    );
}

function sendCodingMessage() {
    var input = document.getElementById("frai-input");
    if (!input) return;

    var text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    _removeAllChips();
    _addBubble(text, "frai-user");
    _showTyping();
    FRAI.sending = true;

    // Snapshot context at send time
    var sendDoctype = FRAI.doctype || "";
    var sendDocname = FRAI.docname || "";

    frappe.call({
        method: "frappe_ai_assistant.api.coding_agent.chat",
        args: {
            message: text,
            doctype: sendDoctype,
            docname: sendDocname,
        },
        callback: function (r) {
            FRAI.sending = false;
            _hideTyping();
            if (!r || !r.message) {
                _addBubble("No response received.", "frai-error");
                return;
            }
            var data = r.message;
            if (data.preview) {
                _showPreviewCard(data.reply, data.preview);
            } else {
                _addBubble(data.reply || "—", "frai-agent");
            }
        },
        error: function (err) {
            FRAI.sending = false;
            _hideTyping();
            _addBubble(
                "Server error. Check that <code>groq_api_key</code> is set in site_config.json.",
                "frai-error"
            );
            console.error("[Frappe AI] coding error:", err);
        },
    });
}

function _showPreviewCard(previewHtml, preview) {
    var msgs = document.getElementById("frai-messages-coding");
    if (!msgs) return;

    FRAI.pendingSessionKey = preview.session_key;

    var card = document.createElement("div");
    card.className = "frai-preview-card";

    var body = document.createElement("div");
    body.className = "frai-preview-body";
    body.innerHTML = previewHtml;

    var actions = document.createElement("div");
    actions.className = "frai-preview-actions";

    var applyBtn  = document.createElement("button");
    applyBtn.className   = "frai-btn-apply";
    applyBtn.textContent = "Apply Changes";

    var cancelBtn = document.createElement("button");
    cancelBtn.className   = "frai-btn-cancel";
    cancelBtn.textContent = "Cancel";

    actions.appendChild(applyBtn);
    actions.appendChild(cancelBtn);

    card.innerHTML = "<h4>Review Changes</h4>";
    card.appendChild(body);
    card.appendChild(actions);

    // Insert before the typing indicator
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
        _applyCodingChange(preview.session_key, card);
    });

    cancelBtn.addEventListener("click", function () {
        card.remove();
        FRAI.pendingSessionKey = null;
        _addBubble("Change cancelled.", "frai-agent");
    });
}

function _applyCodingChange(sessionKey, previewCard) {
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
                _showSuccessCard(data.result, data.change_log);
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

function _showSuccessCard(result, changeLogName) {
    var msgs = document.getElementById("frai-messages-coding");
    if (!msgs) return;

    var card = document.createElement("div");
    card.className = "frai-success-card";
    card.innerHTML =
        "<h4>Applied Successfully</h4>" +
        "<div>" + (result.doctype || "") + ": <strong>" + (result.name || result.label || "") + "</strong>" +
        (result.target ? " on " + result.target : "") + "</div>";

    if (changeLogName) {
        var rollbackBtn = document.createElement("button");
        rollbackBtn.className   = "frai-rollback-link";
        rollbackBtn.textContent = "Undo this change";
        rollbackBtn.addEventListener("click", function () {
            rollbackBtn.textContent = "Undoing…";
            rollbackBtn.disabled    = true;
            _rollbackChange(changeLogName, card);
        });
        card.appendChild(rollbackBtn);
    }

    var reloadBtn = document.createElement("button");
    reloadBtn.className   = "frai-rollback-link";
    reloadBtn.textContent = "Reload page to see changes";
    reloadBtn.style.marginLeft = changeLogName ? "12px" : "0";
    reloadBtn.addEventListener("click", function () { window.location.reload(); });
    card.appendChild(reloadBtn);

    var typing = document.getElementById("frai-typing-coding");
    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(card, typing);
    } else {
        msgs.appendChild(card);
    }
    msgs.scrollTop = msgs.scrollHeight;
}

function _rollbackChange(changeLogName, successCard) {
    frappe.call({
        method: "frappe_ai_assistant.api.coding_agent.rollback",
        args:   { change_log_name: changeLogName },
        callback: function (r) {
            if (successCard) successCard.remove();
            var data = r && r.message;
            if (data && data.success) {
                _addBubble("Rolled back: " + (data.message || changeLogName), "frai-agent");
            } else {
                _addBubble(
                    "Rollback failed: " + (data && data.error || "unknown error"),
                    "frai-error"
                );
            }
        },
        error: function () {
            if (successCard) successCard.remove();
            _addBubble("Rollback failed — server error.", "frai-error");
        },
    });
}