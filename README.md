# Frappe Pilot AI Assistant

**v1.0** — An AI-powered assistant embedded natively inside ERPNext as a Frappe custom app. It lives as a resizable sidebar on every page — no tab switching, no separate tools.

Built as two top-level capabilities: an **Advisor** tab (merged Analyze + Guide) that reads, explains, and navigates the current page, and a **Build** tab with **Chat** and **Changes** (change log) subtabs.

![Frappe Pilot Sidebar](screenshot_ai.png)

---

## What It Does

### Advisor Tab (default)
Reads and analyzes the **specific page or document** you are viewing using a **read-only tool-using agent**, with Guide-style ERPNext navigation knowledge merged in. It fetches data on demand, runs deterministic issue checks, and can surface **clickable desk links** to documents, lists, reports, and setup pages.

- **Open document** — field values, child tables, linked docs, GL entries, workflow state, timeline, automated checks
- **New form** — required fields and form structure from DocType meta
- **List view** — fetches filtered sample rows and counts via `get_list_sample` / `get_list_count`
- **Report** — runs the report with current browser filters via `run_report_sample` (up to 30 rows)
- **Diagnose mode** — triggered by "Diagnose this record" or similar chips; returns Findings / Evidence / Likely cause / What to verify
- **Context-aware suggestion chips** — welcome and follow-up chips adapt to the current form, list, report, or module (e.g. Sales Invoice shows payment/GL/diagnose chips; Pilot Settings shows setup-specific prompts). Logic lives in [`api/suggestions.py`](frappe_pilot/api/suggestions.py) registries — extend the same way as `CHECK_REGISTRY` in `doc_checks.py`.
- **Pilot languages** — In **Pilot Settings > General > Pilot Languages**, **English** is seeded as the first row (required, not removable). Link additional Frappe **Language** rows (e.g. **Kurdish Sorani** / `ckb`, **Arabic** / `ar` / العربية) and check **Enabled**. Only **Enabled** rows appear in the sidebar locale toggle and receive localized suggestion chips / Build cards (when Pilot has a chip catalog for that locale). **Suggestion Chip Languages** (`all_enabled` default, `active_locale`, `active_plus_en`) controls how many locale rows appear in chips. Sorani and Arabic get full UI + split chips when enabled. Other languages use English sidebar chrome with LLM replies in that language. Catalog in [`utils/i18n.py`](frappe_pilot/utils/i18n.py).
- **Smart navigation** — Advisor replies can include desk links. **Pilot Settings > Navigation**: auto-navigate on "go to" requests; optionally close sidebar after navigation.

Evidence line under each reply shows which tools ran and how many issues were found. Conversation history resets when you navigate to a different page.

### Build Tab
Turns plain English into real ERPNext customisations — with a mandatory preview and confirm step before anything touches the database. The welcome capability grid is context-aware: on a Sales Invoice form, quick actions prefill prompts with that DocType.

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

### Build > Changes
Every change the Build agent has applied is listed here with its type, target DocType, and timestamp. Every entry has an Undo button. Rolled-back items are shown with a strikethrough so the audit trail is never erased.

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
| Framework | Frappe v15 / ERPNext v16 |
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
frappe_pilot/
├── public/js/
│   └── ai_sidebar.js               ← entire frontend — injected into every ERPNext page
├── api/
│   ├── analyze.py                  ← Advisor API — merged analyze + guide with navigation
│   ├── context_utils.py            ← Shared doc/meta/route context helpers
│   ├── guide.py                    ← Deprecated shim → analyze.chat
│   └── coding_agent.py             ← Build Agent — tool-calling, validation, rollback
└── frappe_pilot/
    └── doctype/
        └── ai_change_log/          ← Audit trail DocType
```

**How the sidebar gets into ERPNext:**

One line in `hooks.py`:
```python
app_include_js = "/assets/frappe_pilot/js/ai_sidebar.js"
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
bench get-app https://github.com/yourusername/frappe_pilot

# Install on your site
bench --site yoursite.localhost install-app frappe_pilot

# Run migrations (creates the AI Change Log table)
bench --site yoursite.localhost migrate

# Install Python dependency
./env/bin/pip install groq

# Build assets
bench build --app frappe_pilot

# Restart
bench restart
```

### Pilot Settings (desk UI)

Open **Pilot Settings** (desk search or the gear icon in the Pilot sidebar header) to configure:

- **General** — enable/disable Pilot, default tab, **sidebar position** (Right / Left / Bottom), allowed roles. Users can override position per browser via the dock picker in the sidebar header; ↺ resets to the site default.
- **API Keys** — Groq, OpenAI, Gemini password fields (with site_config fallback)
- **Analyze / Guide / Build** — models, token limits, temperatures, tool row caps
- **Advanced** — custom analyze prompt, disabled tools, debug logging

If no API key is configured, opening Pilot shows a setup screen with a **Configure API Keys** button (System Manager only).

**API keys** can be set in Pilot Settings **or** `site_config.json` (Settings fields take precedence):

```json
{
  "groq_api_key": "gsk_your_key_here",
  "groq_api_key_2": "gsk_backup_key",
  "openai_api_key": "sk-...",
  "gemini_api_key": "..."
}
```

---

## Usage

1. Open any page in ERPNext
2. Click the **Pilot** tab on the right edge of the screen
3. Use **Advisor** to summarize, diagnose, or ask how-to questions about the current page
4. Use **Build > Chat** to create customisations in plain English
5. Use **Build > Changes** to review or undo past Build changes

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
| Read full report result rows | Analyze uses route metadata only for reports in v1 |
| Search across all business data | No global query tools — Analyze reads the open document only |
| Create Print Formats, Email Templates, Reports | Not yet implemented |
| Chain two write actions in one confirm | Each tool call is its own preview and confirm cycle |

---

## Roadmap

- [ ] Edit and delete existing customisations
- [ ] Print Format generation
- [ ] Email Template creation
- [x] Advisor tab — merged analyze + guide with smart navigation
- [ ] Report filter + column context in Advisor
- [ ] List row selection context in Advisor
- [ ] Multi-step tool chains in a single conversation turn
- [ ] Support for Claude and OpenAI alongside Groq

---

## License

MIT
