# Forge AI Assistant for ERPNext

**v1.0** — An AI-powered assistant embedded natively inside ERPNext as a Frappe custom app. It lives as a resizable sidebar on every page — no tab switching, no separate tools.

Built as two agents in one sidebar: a **Guide Agent** that answers ERPNext questions in context, and a **Coding Agent** that makes real, validated changes to the system from plain English.

![Forge AI Assistant Sidebar](screenshot_ai.png)

---

## What It Does

### Guide Tab
Answers any question about ERPNext in plain language. Knows exactly what page you are on — form, list view, report, or module — and gives context-aware answers with suggested follow-up questions. Explains DocTypes, workflows, permissions, scripts, and any ERPNext concept without requiring technical knowledge.

Context resets automatically when you navigate to a different page so old page context never bleeds into new answers.

### Build Tab
Turns plain English into real ERPNext customisations — with a mandatory preview and confirm step before anything touches the database.

**The flow:**
```
You type a request
      ↓
Groq (Llama 3.3-70b) decides which tool to call
      ↓
Agent reads DocType schema if needed (read_doctype_meta)
      ↓
Pydantic validates every argument
      ↓
Amber preview card — you see exactly what will be created
      ↓
You click "Apply Changes"
      ↓
Change written to ERPNext
      ↓
Green success card with Undo button
```

Nothing touches the database until you confirm.

### History Tab
Every change the agent has applied is listed here with its type, target DocType, and timestamp. Every entry has an Undo button. Rolled-back items are shown with a strikethrough so the audit trail is never erased.

---

## What the Coding Agent Can Create

| Feature | Description |
|---|---|
| Custom Field | Add a field to any existing DocType — Customer, Sales Invoice, Employee, etc. |
| New DocType | Brand new form and database table, with controller files written to disk |
| Server Script | Python that runs on document events — Before Save, After Save, On Submit, etc. |
| Client Script | JavaScript that runs in the browser on form load or field change |
| Workflow | Multi-stage approval process with states, transitions, and role-based access |
| Records | Insert one or more documents into any existing DocType |

---

## Safety

All of the following are hardcoded and cannot be bypassed:

- **Banned DocTypes** — refuses to touch: `User`, `Role`, `DocType`, `DocField`, `Has Role`, `DocPerm`, `Module Def`, `Patch Log`, `DefaultValue`, `Session Default`
- **System Manager required** — only System Managers can trigger any write action
- **5-minute expiry** — staged changes expire if not confirmed within 5 minutes (stored in Redis with TTL)
- **One action per confirm** — every tool call is a separate preview and confirm cycle
- **Pydantic validation** — every LLM output validated against typed models before staging
- **Mandatory field detection** — agent reads DocType schema before inserting records and fills all required fields

---

## Change Log and Rollback

Every applied change is written to the `AI Change Log` DocType with:
- Who made the change and when
- Change type and target DocType
- Full JSON payload of what was created
- Rollback payload with enough information to reverse it

The **Undo** button calls `rollback()` — deletes the created record from ERPNext and marks the log entry as Rolled Back. The log entry itself is never deleted.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Frappe v15 / ERPNext v15 |
| LLM | Groq API — Llama 3.3-70b-versatile |
| Tool Calling | Groq OpenAI-compatible function calling |
| Validation | Pydantic v2 |
| Frontend | Vanilla JavaScript injected via `app_include_js` hook |
| Styling | Frappe CSS variables — adapts to all Frappe themes |
| Session State | Frappe session + Redis cache |
| Change Log | Custom Frappe DocType (`AI Change Log`) |

---

## Architecture

```
frappe_ai_assistant/
├── public/js/
│   └── ai_sidebar.js               ← entire frontend — injected into every ERPNext page
├── api/
│   ├── guide.py                    ← Guide Agent — Groq chat with page-context awareness
│   └── coding_agent.py             ← Coding Agent — tool-calling loop, validation,
│                                      execution, change log, and rollback
└── frappe_ai_assistant/
    └── doctype/
        └── ai_change_log/          ← Audit trail DocType
```

**How the sidebar gets into ERPNext:**

One line in `hooks.py`:
```python
app_include_js = "/assets/frappe_ai_assistant/js/ai_sidebar.js"
```

Frappe loads this on every desk page. The JS reads `frappe.cur_frm` and `frappe.get_route()` to know exactly what the user is looking at and passes that context to every LLM call.

---

## Coding Agent — Tool-Calling Loop

The agent runs a loop of up to 4 LLM calls per request to support read-then-write patterns:

1. LLM calls `read_doctype_meta` → result fed back immediately (safe read, no confirmation needed)
2. LLM calls an action tool → validated and staged in Redis
3. Frontend shows the amber preview card
4. User confirms → `apply()` executes the change and writes the change log

If `create_documents` is called without a prior schema read, the agent automatically injects the schema and retries so mandatory fields are never missed.

**Dual API key failover** — if the primary Groq key hits a rate limit, the agent switches to `groq_api_key_2` automatically.

---

## Context Detection

The sidebar knows what page you are on at all times:

```javascript
// On a document form
frappe.cur_frm.doctype  // "Customer"
frappe.cur_frm.docname  // "Mehta Traders Pvt Ltd"

// On a list view
frappe.get_route()  // ["List", "Stock Entry", "List"]
// → listDoctype = "Stock Entry"

// On a report
frappe.get_route()  // ["query-report", "General Ledger"]
```

This context is injected as a prefix into every Guide message so the LLM cannot give a generic answer when page context is available:
```
[Context: I am on the Customer List page in ERPNext] what is this page?
```

---

## Installation

**Requirements:**
- Frappe v15 bench
- ERPNext v15
- Groq API key (free at console.groq.com)

**Steps:**

```bash
# Get the app
bench get-app https://github.com/yourusername/frappe_ai_assistant

# Install on your site
bench --site yoursite.localhost install-app frappe_ai_assistant

# Run migrations (creates the AI Change Log table)
bench --site yoursite.localhost migrate

# Install Python dependency
./env/bin/pip install groq

# Build assets
bench build --app frappe_ai_assistant

# Restart
bench restart
```

**Add your Groq API key to site_config.json:**
```json
{
  "groq_api_key": "gsk_your_key_here"
}
```

Optionally add a second key as a rate-limit fallback:
```json
{
  "groq_api_key":   "gsk_primary_key",
  "groq_api_key_2": "gsk_backup_key"
}
```

---

## Usage

1. Open any page in ERPNext
2. Click the **Forge** tab on the right edge of the screen (or press **Alt+A**)
3. Use the **Guide** tab to ask any question about ERPNext
4. Use the **Build** tab to create customisations in plain English
5. Use the **History** tab to review or undo past changes

**Example prompts for the Build tab:**
```
Add a WhatsApp number field to the Customer form
Create a server script that validates GSTIN on Customer save
Add an approval workflow to Purchase Orders with Manager approval
Create a new DocType called Fleet Vehicle with registration, make, model, and year
Seed the Fleet Vehicle DocType with 3 sample records
```

---

## Limitations

| Cannot | Why |
|---|---|
| Edit or delete existing fields or scripts | Creates only — no update tools yet |
| Search or read your business data | No query tools in this version |
| Create Print Formats, Email Templates, Reports | Not yet implemented |
| Chain two write actions in one confirm | Each tool call is its own preview and confirm cycle |

---

## Roadmap

- [ ] Edit and delete existing customisations
- [ ] Print Format generation
- [ ] Email Template creation
- [ ] Query tool — read and summarise business data
- [ ] Multi-step tool chains in a single conversation turn
- [ ] Support for Claude and OpenAI alongside Groq

---

## License

MIT
