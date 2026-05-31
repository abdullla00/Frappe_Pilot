// ============================================================
// ai_sidebar.js
// Place at: frappe_ai_assistant/frappe_ai_assistant/public/js/ai_sidebar.js
// ============================================================

var FRAI = {
    isOpen: false,
    activeTab: "guide",
    doctype: null,
    docname: null,
    isNew: false,
    sending: false,
    panelWidth: 340,
    isResizing: false
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

/* ── Trigger pill ── */
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

/* ── Resize handle ── */
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

/* ── Panel ── */
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
#frai-panel.frai-open {
    transform: translateX(0);
}
#frai-panel.frai-resizing {
    transition: none;
}

/* ── Header ── */
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
#frai-title-wrap { flex:1; min-width:0; }
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

/* ── Tabs ── */
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

/* ── Body ── */
#frai-body {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

/* ── Tab panes ── */
.frai-tab-pane {
    flex: 1;
    display: none;
    flex-direction: column;
    overflow: hidden;
}
.frai-tab-pane.frai-pane-active {
    display: flex;
}

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
    border: 1px solid var(--red-highlight-color, #fbd5d5);
}
.frai-bubble.frai-disabled {
    align-self: flex-start;
    background: var(--yellow-highlight-color, #fffbe6);
    color: var(--text-color, #36414c);
    border: 1px solid var(--yellow-avatar-bg, #fde68a);
}

/* ── Chips ── */
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

/* ── Typing indicator ── */
#frai-typing {
    display: none;
    align-self: flex-start;
    gap: 5px;
    align-items: center;
    padding: 10px 14px;
    background: var(--control-bg, #f4f5f6);
    border: 1px solid var(--border-color, #d1d8dd);
    border-radius: 4px 10px 10px 10px;
}
#frai-typing.frai-visible { display: flex; }
#frai-typing span {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--text-muted, #8d99a6);
    animation: frai-dot .9s infinite;
}
#frai-typing span:nth-child(2) { animation-delay:.15s; }
#frai-typing span:nth-child(3) { animation-delay:.3s; }
@keyframes frai-dot {
    0%,80%,100% { transform:scale(.7); opacity:.4; }
    40%          { transform:scale(1); opacity:1; }
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

/* ── Resize cursor lock ── */
body.frai-is-resizing * {
    cursor: ew-resize !important;
    user-select: none !important;
}
    `;
    document.head.appendChild(style);
}


// ════════════════════════════════════════════════════════════════
// DOM
// ════════════════════════════════════════════════════════════════
function _buildDOM() {

    // ── Trigger pill ─────────────────────────────────────────
    var trigger = document.createElement("div");
    trigger.id = "frai-trigger";
    trigger.setAttribute("title", "Open AI Assistant (Alt+A)");
    trigger.innerHTML =
        '<div id="frai-trigger-dot"></div>' +
        '<span id="frai-trigger-label">AI</span>';
    document.body.appendChild(trigger);

    // ── Panel ────────────────────────────────────────────────
    var panel = document.createElement("div");
    panel.id = "frai-panel";
    panel.setAttribute("role", "complementary");
    panel.setAttribute("aria-label", "AI Assistant");
    panel.innerHTML =

        // Drag handle
        '<div id="frai-resize-handle" title="Drag to resize"></div>' +

        // Header
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
                    '<div id="frai-subtitle">No form open</div>' +
                '</div>' +
                '<button id="frai-close" aria-label="Close">&#10005;</button>' +
            '</div>' +
            '<div id="frai-tabs">' +
                '<button class="frai-tab frai-tab-active" data-tab="guide">Guide</button>' +
                '<button class="frai-tab" data-tab="coding">Coding Agent</button>' +
            '</div>' +
        '</div>' +

        // Body — two independent panes
        '<div id="frai-body">' +

            // Guide pane (visible by default)
            '<div id="frai-pane-guide" class="frai-tab-pane frai-pane-active">' +
                '<div id="frai-messages-guide" class="frai-messages-area">' +
                    '<div id="frai-typing"><span></span><span></span><span></span></div>' +
                '</div>' +
            '</div>' +

            // Coding pane (hidden by default)
            '<div id="frai-pane-coding" class="frai-tab-pane">' +
                '<div id="frai-messages-coding" class="frai-messages-area">' +
                '</div>' +
            '</div>' +

        '</div>' +

        // Footer
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
            var delta    = startX - e.clientX;
            var newWidth = Math.min(600, Math.max(260, startWidth + delta));
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

    // Alt+A shortcut
    document.addEventListener("keydown", function (e) {
        if (e.altKey && e.key === "a") togglePanel();
    });

    // Frappe route change
    if (frappe.router) {
        frappe.router.on("change", function () {
            setTimeout(_updateContext, 400);
        });
    }

    // Form refresh
    $(document).on("form-refresh form-load", function () {
        setTimeout(_updateContext, 200);
    });
}

function _scheduleContextCheck() {
    setTimeout(_updateContext, 900);
}


// ════════════════════════════════════════════════════════════════
// PANEL OPEN / CLOSE
// ════════════════════════════════════════════════════════════════
function togglePanel() {
    FRAI.isOpen ? closePanel() : openPanel();
}

function openPanel() {
    FRAI.isOpen = true;

    var panel   = document.getElementById("frai-panel");
    var trigger = document.getElementById("frai-trigger");

    if (!panel || !trigger) return;

    panel.style.width = FRAI.panelWidth + "px";
    panel.classList.add("frai-open");
    trigger.style.right = FRAI.panelWidth + "px";

    // Show welcome in guide pane only if it is empty
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

    // Update tab button styles
    document.querySelectorAll(".frai-tab").forEach(function (b) {
        b.classList.toggle("frai-tab-active", b.dataset.tab === tab);
    });

    // Show correct pane, hide the other
    document.querySelectorAll(".frai-tab-pane").forEach(function (pane) {
        pane.classList.remove("frai-pane-active");
    });
    var activePane = document.getElementById("frai-pane-" + tab);
    if (activePane) activePane.classList.add("frai-pane-active");

    var input  = document.getElementById("frai-input");
    var sendEl = document.getElementById("frai-send");

    if (tab === "guide") {
        if (input)  { input.placeholder = "Ask anything about ERPNext..."; input.disabled = false; }
        if (sendEl) sendEl.disabled = false;

        // Show welcome only if guide pane is still empty
        var guideMsgs = document.getElementById("frai-messages-guide");
        if (guideMsgs && guideMsgs.querySelectorAll(".frai-bubble").length === 0) {
            _showWelcome();
        }

    } else if (tab === "coding") {
        if (input)  { input.placeholder = "Coding Agent — coming in Phase 2..."; input.disabled = true; }
        if (sendEl) sendEl.disabled = true;

        // Show placeholder only once
        var codingMsgs = document.getElementById("frai-messages-coding");
        if (codingMsgs && codingMsgs.querySelectorAll(".frai-bubble").length === 0) {
            _addBubble(
                "🛠 <strong>Coding Agent — Phase 2</strong><br><br>" +
                "This agent will make real changes to your ERPNext: create Custom Fields, " +
                "write Server Scripts, build Workflows, and more — all from a plain English prompt, " +
                "with a preview-before-apply safety step so nothing runs without your approval.<br><br>" +
                "Use the <strong>Guide tab</strong> to learn how to do these things manually for now.",
                "frai-disabled"
            );
        }
    }
}


// ════════════════════════════════════════════════════════════════
// CONTEXT — reads live Frappe form on every navigation
// ════════════════════════════════════════════════════════════════
function _updateContext() {
    var subtitle = document.getElementById("frai-subtitle");
    if (!subtitle) return;

    if (frappe.cur_frm) {
        FRAI.doctype = frappe.cur_frm.doctype;
        FRAI.docname = frappe.cur_frm.docname;
        FRAI.isNew   = frappe.cur_frm.is_new();

        subtitle.textContent = FRAI.doctype + ": " + (FRAI.isNew ? "(New)" : FRAI.docname);

        // Refresh welcome chips only if guide pane is still empty
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
        var route = (frappe.get_route_str && frappe.get_route_str()) || "Home";
        subtitle.textContent = route;
    }

    console.log("[Frappe AI] Context →", {
        doctype: FRAI.doctype,
        docname: FRAI.docname,
        isNew:   FRAI.isNew
    });
}


// ════════════════════════════════════════════════════════════════
// WELCOME — chips shown only once on first open
// ════════════════════════════════════════════════════════════════
function _showWelcome() {
    var chips = _getContextChips();
    var greet = FRAI.doctype
        ? "I can see you're on the <strong>" + FRAI.doctype + "</strong> form. " +
          "Here are some things I can help you with:"
        : "Hi! I'm your ERPNext Guide. Pick a question below or ask anything:";
    _addBubble(greet, "frai-agent", chips);
}

function _getContextChips() {
    var generic = [
        "What is a DocType?",
        "How do I add a custom field?",
        "How do workflows work?",
        "How do I set up permissions?"
    ];

    var map = {
        "Customer": [
            "How do I add a GSTIN field?",
            "How do I set a credit limit?",
            "How do I link contacts to this customer?",
            "How do I create a Sales Order from here?"
        ],
        "Supplier": [
            "How do I track outstanding payments?",
            "How do I set default payment terms?",
            "How do I add a PAN number field?",
            "How do I block a supplier?"
        ],
        "Sales Invoice": [
            "What happens when I submit this?",
            "How do I apply a discount?",
            "How do I create a credit note?",
            "How do I record a partial payment?"
        ],
        "Purchase Invoice": [
            "How do I match this to a Purchase Order?",
            "How do I record a partial payment?",
            "What is the difference between Save and Submit?",
            "How do I handle a debit note?"
        ],
        "Sales Order": [
            "How do I create an invoice from this order?",
            "How do I check delivery status?",
            "How do I add an approval workflow?",
            "How do I handle a partial delivery?"
        ],
        "Purchase Order": [
            "How do I receive goods against this order?",
            "How do I set up an approval workflow?",
            "How do I create a Purchase Invoice from this?",
            "How do I cancel and amend this order?"
        ],
        "Employee": [
            "How do I set up payroll for this employee?",
            "How do I assign a leave policy?",
            "How do I add an emergency contact field?",
            "How do I track attendance?"
        ],
        "Item": [
            "How do I add item variants?",
            "How do I set a reorder level?",
            "How do I track in multiple warehouses?",
            "What is the difference between stock and non-stock items?"
        ],
        "Payment Entry": [
            "How do I reconcile this against an invoice?",
            "How do I handle foreign currency?",
            "How do I reverse this payment?",
            "What accounts does this affect?"
        ],
        "Stock Entry": [
            "What is the difference between Material Transfer and Issue?",
            "How do I do a stock reconciliation?",
            "How do I track batch numbers?",
            "How do I move stock between warehouses?"
        ],
        "Delivery Note": [
            "How do I create an invoice from this?",
            "How do I track which Sales Order this belongs to?",
            "How do I handle a return?",
            "How do I print this as a packing slip?"
        ],
        "Journal Entry": [
            "When should I use this vs a Payment Entry?",
            "How do I reverse this entry?",
            "How do I reconcile with a bank statement?",
            "What is the difference between debit and credit?"
        ]
    };

    return (FRAI.doctype && map[FRAI.doctype]) ? map[FRAI.doctype] : generic;
}


// ════════════════════════════════════════════════════════════════
// SEND MESSAGE
// ════════════════════════════════════════════════════════════════
function sendMessage() {
    if (FRAI.sending || FRAI.activeTab !== "guide") return;

    var input = document.getElementById("frai-input");
    if (!input) return;

    var text = input.value.trim();
    if (!text) return;

    input.value = "";
    input.style.height = "auto";

    _addBubble(text, "frai-user");
    _showTyping();
    FRAI.sending = true;

    frappe.call({
        method: "frappe_ai_assistant.api.guide.chat",
        args: {
            message: text,
            doctype: FRAI.doctype || "",
            docname: FRAI.docname || "",
            mode:    "guide"
        },
        callback: function (r) {
            FRAI.sending = false;
            _hideTyping();
            if (r && r.message) {
                // No chips on regular responses — only welcome gets chips
                _addBubble(r.message.reply || "—", "frai-agent");
            } else {
                _addBubble("No response received.", "frai-error");
            }
        },
        error: function (err) {
            FRAI.sending = false;
            _hideTyping();
            _addBubble(
                "Could not reach the server. Check that <code>gemini_api_key</code> " +
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

// chips is optional — only _showWelcome() passes it
function _addBubble(html, cssClass, chips) {
    var msgs   = _getActiveMsgs();
    var typing = document.getElementById("frai-typing");

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

    // Insert before typing indicator if it lives in this pane
    if (typing && msgs.contains(typing)) {
        msgs.insertBefore(bubble, typing);
    } else {
        msgs.appendChild(bubble);
    }

    _scrollBottom();
}

// Remove chips after user picks one
function _removeAllChips() {
    document.querySelectorAll(".frai-chips").forEach(function (el) {
        el.remove();
    });
}

function _showTyping() {
    var t = document.getElementById("frai-typing");
    if (t) t.classList.add("frai-visible");
    _scrollBottom();
}

function _hideTyping() {
    var t = document.getElementById("frai-typing");
    if (t) t.classList.remove("frai-visible");
}

function _scrollBottom() {
    var msgs = _getActiveMsgs();
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
}