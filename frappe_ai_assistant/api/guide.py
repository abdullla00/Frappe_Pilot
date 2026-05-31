# ============================================================
# guide.py
# Place at: frappe_ai_assistant/frappe_ai_assistant/api/guide.py
# ============================================================

import frappe


GUIDE_SYSTEM_PROMPT = """
You are an expert ERPNext and Frappe Framework assistant embedded as a sidebar
inside ERPNext. You help non-technical business users understand ERPNext clearly.

## Your tone
- Use plain, simple English first. Then add technical terms if needed.
- Keep answers short and focused — you are a sidebar, not a full page.
- Always tell the user WHERE to click, not just WHAT to do.
- End with one follow-up suggestion when helpful.

## CRITICAL RULE — Current page awareness
Every user message starts with a [Context: ...] tag telling you exactly where
the user is. You MUST use this in every answer.
- If asked "what page am I on", "where am I", "what is this page" —
  answer DIRECTLY and CONFIDENTLY from the [Context] tag.
- Never say "I don't have specific information about your current page."
- Never give a generic answer when a [Context] tag is present.
- The [Context] tag is always accurate and always tells you exactly where they are.

## Core ERPNext knowledge

### What is Frappe / ERPNext?
Frappe is the web framework. ERPNext is the business application built on top of it.
Everything in Frappe is a DocType — a database table + a web form + a REST API in one.

### Key DocTypes and where to find them
- Customer: Selling > Customer
- Supplier: Buying > Supplier
- Sales Invoice: Accounts > Sales Invoice
- Purchase Invoice: Accounts > Purchase Invoice
- Sales Order: Selling > Sales Order
- Purchase Order: Buying > Purchase Order
- Item: Stock > Item
- Employee: HR > Employee
- Payment Entry: Accounts > Payment Entry
- Journal Entry: Accounts > Journal Entry
- Delivery Note: Stock > Delivery Note
- Stock Entry: Stock > Stock Entry
- Purchase Receipt: Stock > Purchase Receipt
- Warehouse: Stock > Warehouse
- Lead: CRM > Lead
- Opportunity: CRM > Opportunity
- Quotation: Selling > Quotation
- Social Login Key: Integrations > Social Login Key

### ERPNext modules
- Selling: Customers, Sales Orders, Sales Invoices, Quotations, Delivery Notes
- Buying: Suppliers, Purchase Orders, Purchase Invoices, Supplier Quotations
- Stock: Items, Warehouses, Stock Entries, Delivery Notes, Purchase Receipts
- Accounts: Ledgers, Journal Entries, Payment Entries, Bank Reconciliation
- HR: Employees, Attendance, Payroll, Leave Management
- Integrations: Social Login Key, Connected Apps, OAuth, REST API settings
- Projects: Projects, Tasks, Timesheets
- Manufacturing: Work Orders, BOMs, Production Planning
- CRM: Leads, Opportunities, Campaigns

### Customization layers (safest to most complex)
1. Custom Fields — add fields to any form. No code. Setup > Custom Field.
2. Property Setters — change field properties (mandatory, hidden, label).
3. Client Scripts — JavaScript in the browser on form load or field change.
4. Server Scripts — Python on save, submit, cancel events.
5. Workflows — approval stages with roles and email alerts. Setup > Workflow.
6. Custom DocTypes — create entirely new forms and tables.
7. Custom Apps — full Python/JS apps installed on the bench.

### Common questions
Q: How do I add a custom field?
A: Setup > Customize Form. Select the DocType. Click Add Row, fill Label and
   Field Type, Save. The field appears immediately — no coding needed.

Q: How do I make a field mandatory?
A: Setup > Customize Form, find the field, check Mandatory, Save.

Q: How do workflows work?
A: A Workflow defines approval stages. Example: Purchase Order goes
   Draft > Submitted > Manager Approved > Finance Approved.
   Each stage has a Role. Go to Setup > Workflow to create one.

Q: What is a DocType?
A: The building block of everything in ERPNext. A DocType is simultaneously
   a database table, a web form, and a REST API.

Q: Why is my document stuck in Draft?
A: It has not been Submitted. Click Submit at the top right. If Submit is not
   visible, a Workflow may require approval first.

Q: What is the difference between Save and Submit?
A: Save keeps the document editable. Submit finalizes it — read-only and
   creates accounting or stock entries.

Q: How do I cancel a submitted document?
A: Open the document, click Cancel at the top right. Some documents require
   a return or credit note instead.

Q: What is bench?
A: Command-line tool for Frappe/ERPNext.
   bench start, bench migrate, bench new-app, bench backup.

Q: How do I set permissions?
A: Setup > Role Permissions Manager. Choose DocType and Role.
   Set Read, Write, Create, Delete, Submit, Cancel.

Q: What is Social Login Key?
A: Social Login Keys let users log into ERPNext using external providers
   like Google, GitHub, or Facebook (OAuth2). Found under Integrations.
   Each key stores a Client ID and Client Secret from the provider.

## Rules
- Never claim to make changes in Guide mode — you only explain.
- If unsure, say so honestly.
- Always mention WHERE in the ERPNext menu a feature is found.
- Always answer "what page am I on" from the [Context] tag.
"""


# ════════════════════════════════════════════════════════════════
# MAIN ENDPOINT
# ════════════════════════════════════════════════════════════════

@frappe.whitelist()
def chat(message, doctype="", docname="", mode="guide", route="", list_doctype=""):
    """
    Called from the browser via frappe.call().
    Returns: { reply: str, chips: [] }
    """

    api_key = frappe.conf.get("groq_api_key")

    if not api_key:
        return {
            "reply": (
                "Groq API key not configured. Please add 'groq_api_key' to "
                "your site_config.json file. Get a free key at console.groq.com."
            ),
            "chips": []
        }

    # ── Build context block for system prompt ─────────────────
    context_block = build_context_block(doctype, docname, mode, route, list_doctype)
    system_prompt  = GUIDE_SYSTEM_PROMPT + "\n\n" + context_block

    # ── Session history ───────────────────────────────────────
    session_key = "ai_guide_history"
    history = frappe.session.get(session_key) or []

    # Reset history when user navigates to a different page
    # so old page context does not bleed into new answers
    last_context    = frappe.session.get("ai_last_context") or ""
    current_context = f"{doctype}|{list_doctype}|{route}"

    if last_context != current_context:
        history = []
        frappe.session["ai_last_context"] = current_context

    # Keep last 20 messages to stay within token limits
    if len(history) > 20:
        history = history[-20:]

    # ── Inject context directly into the user message ─────────
    # This makes it impossible for the AI to ignore the current page.
    # The [Context: ...] prefix is prepended to every message.
    if list_doctype:
        prefix = f"[Context: I am currently on the {list_doctype} List page in ERPNext] "
    elif doctype and docname:
        prefix = f"[Context: I am on the {doctype} form, document: {docname}] "
    elif doctype:
        prefix = f"[Context: I am on a new {doctype} form in ERPNext] "
    elif route:
        prefix = f"[Context: My current page route is '{route}'] "
    else:
        prefix = "[Context: I am on the ERPNext home dashboard] "

    history.append({"role": "user", "content": prefix + message})

    # ── Call Groq ─────────────────────────────────────────────
    try:
        from groq import Groq

        client = Groq(api_key=api_key)

        messages_with_system = [
            {"role": "system", "content": system_prompt}
        ] + history

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages_with_system,
            max_tokens=600,
            temperature=0.7
        )

        reply_text = response.choices[0].message.content

        # Save assistant reply to history
        history.append({"role": "assistant", "content": reply_text})
        frappe.session[session_key] = history

        return {
            "reply": reply_text,
            "chips": []
        }

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "AI Guide Error")
        return {
            "reply": (
                "Something went wrong calling Groq. Error: " + str(e) +
                ". Check the Error Log in ERPNext for details."
            ),
            "chips": []
        }


# ════════════════════════════════════════════════════════════════
# CONTEXT BUILDER — for the system prompt
# ════════════════════════════════════════════════════════════════

def build_context_block(doctype, docname, mode, route="", list_doctype=""):
    lines = [
        "## Current page context",
        "Use this information when answering questions about what page the user is on.",
        ""
    ]

    if doctype:
        # User is on a specific document form
        lines.append(f"The user is on the **{doctype}** form in ERPNext.")

        if docname:
            lines.append(f"Document open: **{docname}**")
        else:
            lines.append("It is a new unsaved document.")

        # Fetch fields so AI knows the form structure
        try:
            meta = frappe.get_meta(doctype)
            field_names = [
                f.label for f in meta.fields
                if f.fieldtype not in (
                    "Column Break", "Section Break", "HTML",
                    "Tab Break", "Heading"
                )
            ][:20]
            if field_names:
                lines.append(f"Fields on this form: {', '.join(field_names)}.")
        except Exception:
            pass

        lines.append(
            f"If asked 'what page am I on' — the user is on the **{doctype}** form."
        )

        if mode == "explain":
            lines.append(
                f"The user clicked Explain. Explain what the {doctype} form is "
                f"for, where to find it in the menu, and what the key fields mean. "
                f"Keep it under 100 words."
            )

    elif list_doctype:
        # User is on a List view
        lines.append(f"The user is on the **{list_doctype} List** page.")
        lines.append(
            f"This shows all {list_doctype} records. Users can search, filter, "
            f"create new records, or click a record to open its form."
        )
        lines.append(
            f"If asked 'what page am I on' — the user is on the "
            f"**{list_doctype} list page**."
        )

    elif route:
        # User is on a report, dashboard, module page, etc.
        lines.append(f"Current route: **{route}**")
        lines.append(
            "Route translation guide:\n"
            "  'List > X > List'              → X List page\n"
            "  'query-report > X'             → X Report page\n"
            "  'Report > X'                   → X Report page\n"
            "  'Buying'                        → Buying module home\n"
            "  'Selling'                       → Selling module home\n"
            "  'Stock'                         → Stock module home\n"
            "  'Accounts'                      → Accounts module home\n"
            "  'HR'                            → HR module home\n"
            "  'Integrations'                  → Integrations module home\n"
            "  'dashboard'                     → Dashboard page\n"
            "  'modules'                       → ERPNext home / all modules\n"
            f"Translate route '{route}' using this logic and answer confidently."
        )

    else:
        lines.append("The user is on the ERPNext home dashboard.")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════
# CLEAR HISTORY
# ════════════════════════════════════════════════════════════════

@frappe.whitelist()
def clear_history():
    """Clears conversation history for the current session."""
    frappe.session["ai_guide_history"]   = []
    frappe.session["ai_last_context"]    = ""
    return {"status": "ok", "message": "Conversation cleared."}