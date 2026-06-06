import json

import frappe
from pydantic import BaseModel, ValidationError, field_validator


# ════════════════════════════════════════════════════════════════
# Safety config
# ════════════════════════════════════════════════════════════════

BANNED_DOCTYPES = frozenset({
	"User", "Role", "DocType", "DocField", "Has Role", "DocPerm",
	"Module Def", "Patch Log", "DefaultValue", "Session Default",
})

VALID_FIELD_TYPES = [
	"Data", "Text", "Long Text", "Small Text", "Select", "Check",
	"Int", "Float", "Currency", "Date", "Datetime", "Time",
	"Link", "Attach", "Attach Image", "Read Only",
]

VALID_SCRIPT_EVENTS = [
	"Before Insert", "Before Validate", "Before Save", "After Save",
	"Before Submit", "After Submit", "Before Cancel", "After Cancel",
	"Before Delete", "After Delete",
]


# ════════════════════════════════════════════════════════════════
# Pydantic models
# ════════════════════════════════════════════════════════════════

class CustomFieldInput(BaseModel):
	doctype: str
	fieldname: str
	label: str
	fieldtype: str
	insert_after: str | None = None
	mandatory: bool = False
	options: str | None = None
	description: str | None = None

	@field_validator("doctype")
	@classmethod
	def no_banned_doctype(cls, v):
		if v in BANNED_DOCTYPES:
			raise ValueError(f"Modifying '{v}' is not allowed for safety reasons.")
		return v

	@field_validator("fieldtype")
	@classmethod
	def valid_fieldtype(cls, v):
		if v not in VALID_FIELD_TYPES:
			raise ValueError(f"Invalid fieldtype '{v}'. Must be one of: {', '.join(VALID_FIELD_TYPES)}")
		return v

	@field_validator("fieldname")
	@classmethod
	def normalise_fieldname(cls, v):
		return v.lower().replace(" ", "_").replace("-", "_")


class ServerScriptInput(BaseModel):
	name: str
	reference_doctype: str
	doctype_event: str
	script: str

	@field_validator("reference_doctype")
	@classmethod
	def no_banned_doctype(cls, v):
		if v in BANNED_DOCTYPES:
			raise ValueError(f"Writing scripts for '{v}' is not allowed.")
		return v

	@field_validator("doctype_event")
	@classmethod
	def valid_event(cls, v):
		if v not in VALID_SCRIPT_EVENTS:
			raise ValueError(f"Invalid event '{v}'. Must be one of: {', '.join(VALID_SCRIPT_EVENTS)}")
		return v


class ClientScriptInput(BaseModel):
	name: str
	dt: str
	script: str
	view: str = "Form"

	@field_validator("dt")
	@classmethod
	def no_banned_doctype(cls, v):
		if v in BANNED_DOCTYPES:
			raise ValueError(f"Writing client scripts for '{v}' is not allowed.")
		return v

	@field_validator("view")
	@classmethod
	def valid_view(cls, v):
		return v if v in ("Form", "List") else "Form"


VALID_DOCTYPE_FIELD_TYPES = [
	"Data", "Int", "Float", "Currency", "Select", "Check",
	"Date", "Datetime", "Time", "Duration", "Link", "Text",
	"Long Text", "Small Text", "Read Only", "Attach", "Attach Image",
]

AUTONAME_MAP = {
	"Set by user":   "",               # user types the name manually
	"Autoincrement": "autoincrement",
	"Random":        "hash",
	"Expression":    None,             # expression supplied via autoname_expression
}


class DocTypeFieldSpec(BaseModel):
	label: str
	fieldtype: str
	mandatory: bool = False
	non_negative: bool = False
	read_only: bool = False
	options: str | None = None
	fetch_from: str | None = None   # e.g. "source_airport.airport_code"

	@field_validator("fieldtype")
	@classmethod
	def valid_fieldtype(cls, v):
		if v not in VALID_DOCTYPE_FIELD_TYPES:
			raise ValueError(f"Invalid fieldtype '{v}'. Supported: {', '.join(VALID_DOCTYPE_FIELD_TYPES)}")
		return v


class CreateDocTypeInput(BaseModel):
	name: str
	naming_rule: str = "Set by user"
	autoname_expression: str | None = None   # used when naming_rule == "Expression"
	fields_json: str | list                  # LLM may send pre-parsed list or JSON string
	is_submittable: bool = False

	@field_validator("fields_json", mode="before")
	@classmethod
	def coerce_fields_json(cls, v):
		# LLM sometimes sends an already-parsed list; convert it back to a string
		# so parse_fields() always works with json.loads()
		if isinstance(v, list):
			return json.dumps(v)
		return v

	@field_validator("naming_rule")
	@classmethod
	def valid_naming(cls, v):
		return v if v in AUTONAME_MAP else "Set by user"

	def parse_fields(self) -> list[dict]:
		raw = json.loads(self.fields_json) if isinstance(self.fields_json, str) else self.fields_json
		if not isinstance(raw, list) or not raw:
			raise ValueError("fields_json must be a non-empty JSON array")
		result = []
		for item in raw:
			spec = DocTypeFieldSpec(**item)
			fieldname = spec.label.lower().replace(" ", "_").replace("-", "_")
			row = {
				"fieldname":    fieldname,
				"label":        spec.label,
				"fieldtype":    spec.fieldtype,
				"reqd":         1 if spec.mandatory else 0,
				"non_negative": 1 if spec.non_negative else 0,
				"read_only":    1 if spec.read_only else 0,
				"options":      spec.options or "",
			}
			if spec.fetch_from:
				row["fetch_from"] = spec.fetch_from
				row["read_only"]  = 1   # fetched fields must be read-only
			result.append(row)
		return result


class CreateDocumentsInput(BaseModel):
	doctype: str
	records_json: str

	@field_validator("doctype")
	@classmethod
	def no_banned_doctype(cls, v):
		if v in BANNED_DOCTYPES:
			raise ValueError(f"Creating records in '{v}' is not allowed.")
		# Resolve exact casing from DB so tabAirline isn't queried as tabairline
		import frappe as _frappe
		actual = _frappe.db.get_value("DocType", {"name": v}, "name")
		if not actual:
			rows = _frappe.db.sql(
				"SELECT name FROM `tabDocType` WHERE LOWER(name) = LOWER(%s) LIMIT 1",
				[v], as_dict=True,
			)
			actual = rows[0]["name"] if rows else v
		return actual

	def parse_records(self) -> list[dict]:
		try:
			raw = json.loads(self.records_json)
		except json.JSONDecodeError as exc:
			raise ValueError(f"records_json is not valid JSON: {exc}") from exc
		if not isinstance(raw, list) or not raw:
			raise ValueError("records_json must be a non-empty JSON array")
		return raw


class WorkflowInput(BaseModel):
	"""
	The LLM sends states/transitions as pipe-delimited strings.
	parse() converts them to the list-of-dicts Frappe needs.
	"""
	workflow_name: str
	document_type: str
	states: str       # "Draft:All|Pending Approval:Manager"
	transitions: str  # "Draft>Submit>Pending Approval:All|Pending Approval>Approve>Approved:Manager"

	@field_validator("document_type")
	@classmethod
	def no_banned_doctype(cls, v):
		if v in BANNED_DOCTYPES:
			raise ValueError(f"Workflows on '{v}' are not allowed.")
		return v

	def parse_states(self) -> list[dict]:
		result = []
		for part in self.states.split("|"):
			part = part.strip()
			if not part:
				continue
			if ":" in part:
				state, role = part.rsplit(":", 1)
			else:
				state, role = part, "All"
			result.append({"state": state.strip(), "doc_status": "0", "allow_edit": role.strip()})
		if not result:
			raise ValueError("states string produced no valid states")
		return result

	def parse_transitions(self) -> list[dict]:
		result = []
		for part in self.transitions.split("|"):
			part = part.strip()
			if not part:
				continue
			# Format: FromState>ActionLabel>ToState:AllowedRole
			if ":" in part:
				arrow_part, role = part.rsplit(":", 1)
			else:
				arrow_part, role = part, "All"
			segs = arrow_part.split(">")
			if len(segs) != 3:
				raise ValueError(f"Transition segment must have 3 parts separated by '>': {part!r}")
			result.append({
				"state":      segs[0].strip(),
				"action":     segs[1].strip(),
				"next_state": segs[2].strip(),
				"allowed":    role.strip(),
			})
		if not result:
			raise ValueError("transitions string produced no valid transitions")
		return result


# ════════════════════════════════════════════════════════════════
# LLM tool definitions (Groq / OpenAI schema)
# ════════════════════════════════════════════════════════════════

TOOLS = [
	{
		"type": "function",
		"function": {
			"name": "create_doctype",
			"description": "Create a brand-new DocType (new database table + form) in ERPNext",
			"parameters": {
				"type": "object",
				"properties": {
					"name": {"type": "string", "description": "DocType name, e.g. 'Airline'"},
					"naming_rule": {
						"type": "string",
						"enum": ["Set by user", "Autoincrement", "Random", "Expression"],
						"description": (
							"How records are named. Use 'Expression' for custom patterns "
							"like '{flight}-{source_airport_code}-to-{destination_airport_code}-{####}'. "
							"Default: Set by user."
						),
					},
					"autoname_expression": {
						"type": "string",
						"description": (
							"Required when naming_rule is 'Expression'. "
							"Frappe naming expression using field names in braces. "
							"Use {####} for a padded sequence number. "
							"Example: '{flight}-{source_airport_code}-to-{destination_airport_code}-{####}'"
						),
					},
					"fields_json": {
						"type": "string",
						"description": (
							'JSON array of field definitions. '
							'Each item: {"label":"str","fieldtype":"str","mandatory":bool,'
							'"non_negative":bool,"read_only":bool,"options":"str or null",'
							'"fetch_from":"fieldname.child_field or null"}. '
							'Supported fieldtypes: Data, Int, Float, Currency, Select, Check, '
							'Date, Datetime, Time, Duration, Link, Text, Long Text, Read Only, Attach. '
							'For fetch_from fields: set read_only to true and fieldtype to Data '
							'(not Read Only). fetch_from format: "link_fieldname.source_fieldname".'
						),
					},
					"is_submittable": {
						"type": "boolean",
						"description": "Whether records in this DocType can be submitted",
					},
				},
				"required": ["name", "fields_json"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "create_documents",
			"description": "Create one or more records (documents) in any existing DocType",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string", "description": "The DocType to create records in"},
					"records_json": {
						"type": "string",
						"description": (
							'JSON array of records. Each item is a dict of fieldname:value pairs. '
							'For "Set by user" DocTypes include a "name" key. '
							'Example: [{"name":"IndiGo","headquarters":"Gurugram","founding_year":2006},'
							'{"name":"AirAsia","headquarters":"Kuala Lumpur","founding_year":1993}]'
						),
					},
				},
				"required": ["doctype", "records_json"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "read_doctype_meta",
			"description": (
				"Read the existing fields of a DocType. "
				"ALWAYS call this before create_custom_field so you know what already exists."
			),
			"parameters": {
				"type": "object",
				"properties": {
					"doctype": {"type": "string", "description": "DocType name to inspect"}
				},
				"required": ["doctype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "create_custom_field",
			"description": "Add a custom field to any DocType",
			"parameters": {
				"type": "object",
				"properties": {
					"doctype":      {"type": "string"},
					"fieldname":    {"type": "string", "description": "snake_case, e.g. gstin_number"},
					"label":        {"type": "string"},
					"fieldtype":    {
						"type": "string",
						"enum": VALID_FIELD_TYPES,
					},
					"insert_after": {"type": "string", "description": "fieldname to insert after (optional)"},
					"mandatory":    {"type": "boolean"},
					"options":      {
						"type": "string",
						"description": "For Select: newline-separated options. For Link: linked DocType name.",
					},
					"description":  {"type": "string", "description": "Help text shown under the field"},
				},
				"required": ["doctype", "fieldname", "label", "fieldtype"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "create_server_script",
			"description": "Create a Server Script that runs Python on a document event",
			"parameters": {
				"type": "object",
				"properties": {
					"name":              {"type": "string", "description": "Unique script name (snake_case)"},
					"reference_doctype": {"type": "string"},
					"doctype_event":     {"type": "string", "enum": VALID_SCRIPT_EVENTS},
					"script":            {
						"type": "string",
						"description": "Python body. Use doc and frappe objects — no imports needed.",
					},
				},
				"required": ["name", "reference_doctype", "doctype_event", "script"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "create_client_script",
			"description": "Create a Client Script that runs JavaScript on a form or list view",
			"parameters": {
				"type": "object",
				"properties": {
					"name":   {"type": "string"},
					"dt":     {"type": "string", "description": "DocType this script runs on"},
					"script": {
						"type": "string",
						"description": "JavaScript using frappe.ui.form.on(dt, {...}) pattern",
					},
					"view":   {"type": "string", "enum": ["Form", "List"]},
				},
				"required": ["name", "dt", "script"],
			},
		},
	},
	{
		"type": "function",
		"function": {
			"name": "create_workflow",
			"description": "Create an approval workflow on a DocType",
			"parameters": {
				"type": "object",
				"properties": {
					"workflow_name": {"type": "string"},
					"document_type": {"type": "string"},
					"states": {
						"type": "string",
						"description": (
							"Pipe-separated states. Format: StateName:EditRole|StateName:EditRole. "
							"Example: 'Draft:All|Pending Approval:Purchase Manager|Approved:Accounts Manager'"
						),
					},
					"transitions": {
						"type": "string",
						"description": (
							"Pipe-separated transitions. Format: FromState>ActionLabel>ToState:AllowedRole. "
							"Example: 'Draft>Submit>Pending Approval:All|Pending Approval>Approve>Approved:Purchase Manager'"
						),
					},
				},
				"required": ["workflow_name", "document_type", "states", "transitions"],
			},
		},
	},
]


# ════════════════════════════════════════════════════════════════
# System prompt
# ════════════════════════════════════════════════════════════════

CODING_SYSTEM_PROMPT = """
You are an expert ERPNext Coding Agent embedded as a sidebar inside ERPNext.
You make REAL changes to ERPNext by calling tools. Every change is shown to the user for review before it is applied.

## Available tools
1. create_doctype — create a brand-new DocType (new database table + form).
2. create_documents — insert one or more records into any DocType.
3. read_doctype_meta — read existing fields. ALWAYS call this before create_custom_field.
4. create_custom_field — add a field to an existing DocType.
5. create_server_script — write Python that runs on document events.
6. create_client_script — write JavaScript that runs on form load or field change.
7. create_workflow — build an approval workflow on a DocType.

## Rules
- If the user asks to undo, rollback, revert, or cancel a change, do NOT call any tool.
  Reply with plain text: "To undo a change, click the **Undo this change** link in the
  green success card above. You can also find all changes in the AI Change Log."
- Use create_doctype when the user asks to create a new DocType, master, or table.
- Use create_documents to insert sample or seed records into a DocType.
- If the user asks to create a DocType AND seed records, call create_doctype first,
  then create_documents in the SAME response as two sequential tool calls — but since
  you can only call one tool per response, call create_doctype first. The user will
  confirm and apply it, then you will call create_documents.
- ALWAYS call read_doctype_meta before create_documents. Read the field list, find every
  field where reqd=true, and include a realistic value for each mandatory field in every
  record. Never guess field names — read the meta first, then insert.
- ALWAYS call read_doctype_meta first before create_custom_field.
- Never target: User, Role, DocType, DocField, Has Role, DocPerm.
- For fields_json use valid JSON array. Each item: label, fieldtype, mandatory (bool), non_negative (bool), read_only (bool), options (str|null), fetch_from (str|null).
- fetch_from format: "link_fieldname.target_fieldname" e.g. "source_airport.airport_code". Always set read_only:true for fetch_from fields.
- Fetched fields should use fieldtype "Data" (not "Read Only") so Frappe can write the fetched value.
- For Expression naming: set naming_rule to "Expression" and provide autoname_expression like "{flight}-{source_airport_code}-to-{destination_airport_code}-{####}". Use {####} for a padded counter.
- Never put the naming example output as the naming_rule value — naming_rule must always be one of the enum values.
- For records_json use valid JSON array. Each item is a dict of fieldname:value pairs.
- For "Set by user" DocTypes always include "name" key in each record.
- fieldname in records must be snake_case (e.g. "founding_year", not "Founding Year").
- Server scripts: `doc` and `frappe` are available — no imports needed.
- Client scripts: use `frappe.ui.form.on(dt, { refresh: function(frm) {} })` pattern.
- For workflows: states format is "State:Role|State:Role", transitions is "From>Action>To:Role|...".
- If the request is ambiguous ask exactly one clarifying question before calling any tool.
- Do NOT narrate — just call the right tool.
"""


# ════════════════════════════════════════════════════════════════
# Public endpoints
# ════════════════════════════════════════════════════════════════

def _get_groq_client():
	"""
	Return a Groq client using the primary key, or the backup key
	(groq_api_key_2) if the primary is missing.  Returns (client, key_label).
	"""
	from groq import Groq
	primary = frappe.conf.get("groq_api_key")
	backup  = frappe.conf.get("groq_api_key_2")
	if primary:
		return Groq(api_key=primary), "primary"
	if backup:
		return Groq(api_key=backup), "backup"
	return None, None


def _coding_system_prompt():
	from frappe_pilot.utils.i18n import get_llm_language_instruction
	from frappe_pilot.utils.settings import get_enabled_languages

	return CODING_SYSTEM_PROMPT + get_llm_language_instruction(get_enabled_languages())


@frappe.whitelist()
def chat(message, history="", doctype="", docname=""):
	"""
	Analyse the user's plain-English request with the LLM.
	Executes read_doctype_meta immediately (safe).
	For action tools returns a preview dict — nothing is applied yet.
	Accepts an optional `history` JSON array of prior {role, content} pairs
	so the LLM retains context across multiple turns in the same session.
	"""
	from frappe_pilot.utils.llm import chat_completion, get_active_provider, has_api_key
	from frappe_pilot.utils.settings import get_build_config, user_has_build_access

	build_cfg = get_build_config()
	if not build_cfg.get("enabled"):
		return _err("The Build tab is disabled in Pilot Settings.")

	if not user_has_build_access():
		return _err("You do not have permission to use the Build agent.")

	if not has_api_key():
		return {"reply": None, "needs_api_setup": True, "preview": None}

	if get_active_provider() not in ("Groq", "OpenAI"):
		return _err("Build agent requires Groq or OpenAI as the active LLM provider.")

	# Parse conversation history for multi-turn context (last 7 pairs = 14 msgs)
	history_msgs = []
	if history:
		try:
			parsed = json.loads(history)
			history_msgs = [
				m for m in parsed
				if isinstance(m, dict)
				and m.get("role") in ("user", "assistant")
				and isinstance(m.get("content"), str)
			][-14:]
		except Exception:
			pass

	from frappe_pilot.utils.i18n import detect_user_locale, locale_context_note
	from frappe_pilot.utils.settings import get_enabled_languages

	user_locale = detect_user_locale(message, get_enabled_languages())
	user_content = locale_context_note(user_locale) + message

	messages = [
		{"role": "system", "content": _coding_system_prompt()},
		*history_msgs,
		{"role": "user", "content": user_content},
	]

	def _call_llm(msgs, use_tools=True):
		response, _, _ = chat_completion(
			messages=msgs,
			model=build_cfg["model"],
			max_tokens=build_cfg["max_tokens"] if use_tools else build_cfg["max_tokens_fallback"],
			temperature=build_cfg["temperature"] if use_tools else build_cfg["temperature_fallback"],
			tools=TOOLS if use_tools else None,
			tool_choice="auto" if use_tools else None,
		)
		return response

	# Tool-calling loop — supports read → write patterns (up to 4 LLM calls)
	for _pass in range(4):
		try:
			response = _call_llm(messages)
		except Exception as exc:
			exc_str = str(exc)
			if "rate_limit_exceeded" in exc_str or "429" in exc_str:
				import re
				wait = re.search(r"try again in ([^\\.,']+)", exc_str)
				wait_msg = f" Try again in {wait.group(1)}." if wait else ""
				return _err(f"Groq rate limit reached — both API keys exhausted.{wait_msg}")
			# Groq raises BadRequestError with code=tool_use_failed when the model
			# generates a blank or malformed tool call. Retry without tools so the
			# user gets a helpful clarification instead of a hard error.
			if "tool_use_failed" in exc_str:
				try:
					fallback = _call_llm(messages, use_tools=False)
				except Exception:
					return _err("I need more details to proceed. Could you rephrase?")
				return {
					"reply": fallback.choices[0].message.content
					         or "I need more details to proceed. Could you rephrase?",
					"preview": None,
				}
			raise

		msg = response.choices[0].message

		if not msg.tool_calls:
			# Pure text — clarification question or polite refusal
			return {"reply": msg.content or "I need more information to help with that.", "preview": None}

		tool_call = msg.tool_calls[0]
		tool_name  = tool_call.function.name
		tool_args  = json.loads(tool_call.function.arguments)

		if tool_name == "read_doctype_meta":
			# Safe read — execute immediately and feed result back
			result = _exec_read_doctype_meta(tool_args.get("doctype", ""))
			messages.append({
				"role":    "assistant",
				"content": None,
				"tool_calls": [{
					"id":   tool_call.id,
					"type": "function",
					"function": {
						"name":      tool_name,
						"arguments": tool_call.function.arguments,
					},
				}],
			})
			messages.append({
				"role":         "tool",
				"tool_call_id": tool_call.id,
				"content":      json.dumps(result),
			})
			continue  # Ask LLM what to do next

		# create_documents without a prior meta read — inject schema and retry
		if tool_name == "create_documents":
			doctype = tool_args.get("doctype", "")
			already_have_meta = any(
				m.get("role") == "tool" and
				m.get("content", "").find(f'"doctype": "{doctype}"') != -1
				for m in messages
			)
			if doctype and not already_have_meta:
				meta = _exec_read_doctype_meta(doctype)
				fake_id = frappe.generate_hash(length=16)
				messages.append({
					"role":    "assistant",
					"content": None,
					"tool_calls": [{
						"id":   fake_id,
						"type": "function",
						"function": {
							"name":      "read_doctype_meta",
							"arguments": json.dumps({"doctype": doctype}),
						},
					}],
				})
				messages.append({
					"role":         "tool",
					"tool_call_id": fake_id,
					"content":      json.dumps(meta),
				})
				continue  # LLM retries with real field list + mandatory flags

		# Action tool — validate and stage
		try:
			validated, preview_html, summary = _validate_and_preview(tool_name, tool_args)
		except (ValidationError, ValueError) as exc:
			return _err(f"Validation error: {exc}")

		session_key = frappe.generate_hash(length=24)
		expiry_sec = int(build_cfg.get("preview_expiry_minutes", 5)) * 60
		frappe.cache().set_value(
			f"ai_coding_{session_key}",
			{"tool": tool_name, "args": validated, "user": frappe.session.user},
			expires_in_sec=expiry_sec,
		)

		return {
			"reply":   preview_html,
			"preview": {
				"session_key": session_key,
				"tool":        tool_name,
				"summary":     summary,
			},
		}

	return _err("I wasn't able to generate a plan for that. Could you rephrase your request?")


@frappe.whitelist()
def apply(session_key):
	"""Apply the staged change after the user confirms the preview."""
	cache_key = f"ai_coding_{session_key}"
	pending   = frappe.cache().get_value(cache_key)

	if not pending:
		return {
			"success": False,
			"error": "Pending change not found — it may have expired (5 min limit). Please start over.",
		}

	if pending.get("user") != frappe.session.user:
		return {"success": False, "error": "Session mismatch."}

	tool_name = pending["tool"]
	args      = pending["args"]

	try:
		result = _execute_tool(tool_name, args)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "AI Coding Agent — apply error")
		return {"success": False, "error": str(exc)}

	frappe.cache().delete_value(cache_key)

	log_name = None
	try:
		log_name = _log_change(tool_name, args, result)
	except Exception:
		# Change log table may not exist yet (bench migrate not run).
		# Log the failure but don't block the successful apply.
		frappe.log_error(frappe.get_traceback(), "AI Coding Agent — change log write failed")

	return {"success": True, "result": result, "change_log": log_name}


@frappe.whitelist()
def rollback(change_log_name):
	"""Delete the record that was created and mark the log as rolled back."""
	try:
		log = frappe.get_doc("AI Change Log", change_log_name)
	except frappe.DoesNotExistError:
		return {"success": False, "error": "Change log not found."}

	if log.status == "Rolled Back":
		return {"success": False, "error": "Already rolled back."}

	rollback_info = json.loads(log.rollback_payload or "{}")

	try:
		_delete_record(
			rollback_info.get("doctype"),
			rollback_info.get("name"),
			rollback_info.get("names"),
		)
	except Exception as exc:
		frappe.log_error(frappe.get_traceback(), "AI Coding Agent — rollback error")
		return {"success": False, "error": str(exc)}

	log.status = "Rolled Back"
	log.save(ignore_permissions=True)
	return {"success": True, "message": f"Rolled back: {log.change_name}"}


@frappe.whitelist()
def get_change_log(limit=10):
	"""Recent changes made by the current user."""
	return frappe.get_all(
		"AI Change Log",
		filters={"user": frappe.session.user},
		fields=["name", "change_type", "target_doctype", "change_name", "status", "applied_at"],
		order_by="applied_at desc",
		limit=int(limit),
	)


# ════════════════════════════════════════════════════════════════
# Tool: read_doctype_meta
# ════════════════════════════════════════════════════════════════

def _exec_read_doctype_meta(doctype):
	if not doctype:
		return {"error": "No DocType specified"}
	if doctype in BANNED_DOCTYPES:
		return {"error": f"Reading '{doctype}' is not allowed"}
	try:
		meta = frappe.get_meta(doctype)
		fields = [
			{
				"fieldname": f.fieldname,
				"label":     f.label or "",
				"fieldtype": f.fieldtype,
				"options":   f.options or "",
				"reqd":      bool(f.reqd),
			}
			for f in meta.fields
			if f.fieldtype not in ("Column Break", "Section Break", "Tab Break", "HTML", "Heading")
			and f.fieldname
		][:40]
		return {
			"doctype":    doctype,
			"total_fields": len(meta.fields),
			"data_fields": fields,
		}
	except frappe.exceptions.DoesNotExistError:
		return {"error": f"DocType '{doctype}' does not exist"}
	except Exception as exc:
		return {"error": str(exc)}


# ════════════════════════════════════════════════════════════════
# Validation + preview generation
# ════════════════════════════════════════════════════════════════

def _validate_and_preview(tool_name, args):
	"""Return (validated_dict, preview_html, summary)."""

	if tool_name == "create_custom_field":
		m = CustomFieldInput(**args)
		v = m.model_dump()
		req_label = "Mandatory" if v["mandatory"] else "Optional"
		lines = [
			f"<strong>DocType:</strong> {v['doctype']}",
			f"<strong>Field:</strong> {v['label']} (<code>{v['fieldname']}</code>)",
			f"<strong>Type:</strong> {v['fieldtype']} &mdash; {req_label}",
		]
		if v.get("options"):
			lines.append(f"<strong>Options:</strong> {v['options'].replace(chr(10), ', ')}")
		if v.get("insert_after"):
			lines.append(f"<strong>After field:</strong> <code>{v['insert_after']}</code>")
		if v.get("description"):
			lines.append(f"<strong>Help text:</strong> {v['description']}")
		html = "<strong>New Custom Field</strong><br><br>" + "<br>".join(lines)
		summary = f"Add '{v['label']}' ({v['fieldtype']}) to {v['doctype']}"
		return v, html, summary

	if tool_name == "create_server_script":
		m = ServerScriptInput(**args)
		v = m.model_dump()
		snippet = v["script"][:400] + ("…" if len(v["script"]) > 400 else "")
		html = (
			f"<strong>New Server Script</strong><br><br>"
			f"<strong>Name:</strong> {v['name']}<br>"
			f"<strong>DocType:</strong> {v['reference_doctype']}<br>"
			f"<strong>Event:</strong> {v['doctype_event']}<br><br>"
			f"<pre style='font-size:10.5px;white-space:pre-wrap;"
			f"background:#f8fafc;padding:8px;border-radius:4px;"
			f"border:1px solid #e2e8f0;margin:0;'>{snippet}</pre>"
		)
		summary = f"Server Script '{v['name']}' on {v['reference_doctype']} {v['doctype_event']}"
		return v, html, summary

	if tool_name == "create_client_script":
		m = ClientScriptInput(**args)
		v = m.model_dump()
		snippet = v["script"][:400] + ("…" if len(v["script"]) > 400 else "")
		html = (
			f"<strong>New Client Script</strong><br><br>"
			f"<strong>Name:</strong> {v['name']}<br>"
			f"<strong>DocType:</strong> {v['dt']}<br>"
			f"<strong>View:</strong> {v['view']}<br><br>"
			f"<pre style='font-size:10.5px;white-space:pre-wrap;"
			f"background:#f8fafc;padding:8px;border-radius:4px;"
			f"border:1px solid #e2e8f0;margin:0;'>{snippet}</pre>"
		)
		summary = f"Client Script '{v['name']}' on {v['dt']} ({v['view']})"
		return v, html, summary

	if tool_name == "create_workflow":
		m = WorkflowInput(**args)
		states      = m.parse_states()
		transitions = m.parse_transitions()
		states_html = "".join(
			f"<li>{s['state']} — editable by <em>{s['allow_edit']}</em></li>"
			for s in states
		)
		trans_html = "".join(
			f"<li>{t['state']} &rarr; <strong>{t['action']}</strong> &rarr; {t['next_state']}"
			f" (role: {t['allowed']})</li>"
			for t in transitions
		)
		html = (
			f"<strong>New Workflow</strong><br><br>"
			f"<strong>Name:</strong> {m.workflow_name}<br>"
			f"<strong>DocType:</strong> {m.document_type}<br><br>"
			f"<strong>States:</strong><ul style='margin:4px 0 8px 16px;padding:0;'>{states_html}</ul>"
			f"<strong>Transitions:</strong><ul style='margin:4px 0 0 16px;padding:0;'>{trans_html}</ul>"
		)
		# Store the parsed lists so apply() doesn't re-parse
		validated = {
			"workflow_name": m.workflow_name,
			"document_type": m.document_type,
			"states":        states,
			"transitions":   transitions,
		}
		summary = f"Workflow '{m.workflow_name}' on {m.document_type} ({len(states)} states)"
		return validated, html, summary

	if tool_name == "create_doctype":
		m      = CreateDocTypeInput(**args)
		fields = m.parse_fields()
		fields_html = "".join(
			f"<li><strong>{f['label']}</strong> ({f['fieldtype']})"
			+ (" — Mandatory" if f["reqd"] else "")
			+ (" — Non-negative" if f["non_negative"] else "")
			+ "</li>"
			for f in fields
		)
		html = (
			f"<strong>New DocType</strong><br><br>"
			f"<strong>Name:</strong> {m.name}<br>"
			f"<strong>Naming:</strong> {m.naming_rule}<br>"
			f"<strong>Submittable:</strong> {'Yes' if m.is_submittable else 'No'}<br><br>"
			f"<strong>Fields ({len(fields)}):</strong>"
			f"<ul style='margin:4px 0 0 16px;padding:0;'>{fields_html}</ul>"
		)
		validated = {
			"name":                m.name,
			"naming_rule":         m.naming_rule,
			"autoname_expression": m.autoname_expression,
			"is_submittable":      m.is_submittable,
			"fields":              fields,
		}
		summary = f"DocType '{m.name}' with {len(fields)} fields"
		return validated, html, summary

	if tool_name == "create_documents":
		m       = CreateDocumentsInput(**args)
		records = m.parse_records()
		rows_html = "".join(
			f"<li>{r.get('name', '(auto)')}: "
			+ ", ".join(f"{k}={v}" for k, v in r.items() if k != "name")
			+ "</li>"
			for r in records
		)
		html = (
			f"<strong>New Records in {m.doctype}</strong><br><br>"
			f"<strong>Count:</strong> {len(records)}<br><br>"
			f"<ul style='margin:4px 0 0 16px;padding:0;'>{rows_html}</ul>"
		)
		validated = {"doctype": m.doctype, "records": records}
		summary   = f"Create {len(records)} record(s) in {m.doctype}"
		return validated, html, summary

	raise ValueError(f"Unknown tool: {tool_name}")


# ════════════════════════════════════════════════════════════════
# Tool execution
# ════════════════════════════════════════════════════════════════

def _execute_tool(tool_name, args):
	dispatch = {
		"create_custom_field":  _apply_custom_field,
		"create_server_script": _apply_server_script,
		"create_client_script": _apply_client_script,
		"create_workflow":      _apply_workflow,
		"create_doctype":       _apply_create_doctype,
		"create_documents":     _apply_create_documents,
	}
	fn = dispatch.get(tool_name)
	if not fn:
		raise ValueError(f"Unknown tool: {tool_name}")
	return fn(args)


def _apply_custom_field(args):
	if frappe.db.exists("Custom Field", {"dt": args["doctype"], "fieldname": args["fieldname"]}):
		raise ValueError(f"Field '{args['fieldname']}' already exists on {args['doctype']}.")
	doc = frappe.get_doc({
		"doctype":      "Custom Field",
		"dt":           args["doctype"],
		"fieldname":    args["fieldname"],
		"label":        args["label"],
		"fieldtype":    args["fieldtype"],
		"insert_after": args.get("insert_after") or "",
		"reqd":         1 if args.get("mandatory") else 0,
		"options":      args.get("options") or "",
		"description":  args.get("description") or "",
	})
	doc.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=args["doctype"])
	return {"name": doc.name, "doctype": "Custom Field", "label": args["label"], "target": args["doctype"]}


def _apply_server_script(args):
	if frappe.db.exists("Server Script", args["name"]):
		raise ValueError(f"Server Script '{args['name']}' already exists.")
	doc = frappe.get_doc({
		"doctype":           "Server Script",
		"name":              args["name"],
		"script_type":       "DocType Event",
		"reference_doctype": args["reference_doctype"],
		"doctype_event":     args["doctype_event"],
		"script":            args["script"],
		"disabled":          0,
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "doctype": "Server Script", "target": args["reference_doctype"]}


def _apply_client_script(args):
	if frappe.db.exists("Client Script", args["name"]):
		raise ValueError(f"Client Script '{args['name']}' already exists.")
	doc = frappe.get_doc({
		"doctype":  "Client Script",
		"name":     args["name"],
		"dt":       args["dt"],
		"script":   args["script"],
		"view":     args.get("view", "Form"),
		"enabled":  1,
	})
	doc.insert(ignore_permissions=True)
	return {"name": doc.name, "doctype": "Client Script", "target": args["dt"]}


def _apply_workflow(args):
	if frappe.db.exists("Workflow", args["workflow_name"]):
		raise ValueError(f"Workflow '{args['workflow_name']}' already exists.")
	doc = frappe.get_doc({
		"doctype":          "Workflow",
		"workflow_name":    args["workflow_name"],
		"document_type":    args["document_type"],
		"is_active":        1,
		"send_email_alert": 0,
		"states": [
			{
				"state":      s["state"],
				"doc_status": s.get("doc_status", "0"),
				"allow_edit": s["allow_edit"],
			}
			for s in args["states"]
		],
		"transitions": [
			{
				"state":      t["state"],
				"action":     t["action"],
				"next_state": t["next_state"],
				"allowed":    t["allowed"],
			}
			for t in args["transitions"]
		],
	})
	doc.insert(ignore_permissions=True)
	frappe.clear_cache(doctype=args["document_type"])
	return {"name": doc.name, "doctype": "Workflow", "target": args["document_type"]}


def _apply_create_doctype(args):
	import pathlib

	name = args["name"]
	if frappe.db.exists("DocType", name):
		raise ValueError(f"DocType '{name}' already exists.")

	naming_rule = args.get("naming_rule", "Set by user")
	if naming_rule == "Expression":
		expr = (args.get("autoname_expression") or "").strip()
		if not expr:
			raise ValueError(
				"naming_rule is 'Expression' but autoname_expression is empty. "
				"Provide a pattern like '{flight}-{source_airport_code}-to-{destination_airport_code}-{####}'."
			)
		autoname = expr
	else:
		autoname = AUTONAME_MAP.get(naming_rule, "")

	# Resolve our app's module — fall back to hardcoded value
	module = "Frappe Pilot"
	try:
		found = frappe.get_all(
			"Module Def",
			filters={"app_name": "frappe_pilot"},
			pluck="name",
			limit=1,
		)
		if found:
			module = found[0]
	except Exception:
		pass

	doc = frappe.get_doc({
		"doctype":        "DocType",
		"name":           name,
		"module":         module,
		"naming_rule":    naming_rule,
		"autoname":       autoname,
		"is_submittable": 1 if args.get("is_submittable") else 0,
		"custom":         1,
		"fields":         args["fields"],
		"permissions": [
			{
				"role":   "System Manager",
				"read":   1, "write":  1, "create": 1,
				"delete": 1, "submit": 0, "cancel": 0,
				"amend":  0, "report": 1, "export": 1,
				"import": 0, "print":  1, "email":  1,
			}
		],
	})
	doc.insert(ignore_permissions=True)
	frappe.clear_cache()

	# ── Write controller files on disk ───────────────────────────
	snake_name  = name.lower().replace(" ", "_")
	pascal_name = "".join(w.title() for w in name.split())

	app_path    = pathlib.Path(frappe.get_app_path("frappe_pilot"))
	doctype_dir = app_path / "doctype"
	doctype_dir.mkdir(parents=True, exist_ok=True)
	# Ensure the doctype/ package itself is importable
	pkg_init = doctype_dir / "__init__.py"
	if not pkg_init.exists():
		pkg_init.write_text("")

	folder = doctype_dir / snake_name
	folder.mkdir(parents=True, exist_ok=True)

	(folder / "__init__.py").write_text("")

	(folder / f"{snake_name}.py").write_text(
		f"import frappe\n"
		f"from frappe.model.document import Document\n\n\n"
		f"class {pascal_name}(Document):\n"
		f"    pass\n"
	)

	doc_dict = frappe.get_doc("DocType", name).as_dict()
	(folder / f"{snake_name}.json").write_text(
		frappe.as_json(doc_dict, indent=1)
	)

	module_snake = module.lower().replace(" ", "_")
	frappe.reload_doc(module_snake, "doctype", snake_name)

	return {"name": name, "doctype": "DocType", "label": name, "target": ""}


def _apply_create_documents(args):
	doctype = args["doctype"]
	# Resolve the exact case the DocType was created with (LLM may send lowercase)
	actual = frappe.db.get_value("DocType", {"name": doctype}, "name")
	if not actual:
		rows = frappe.db.sql(
			"SELECT name FROM `tabDocType` WHERE LOWER(name) = LOWER(%s) LIMIT 1",
			[doctype], as_dict=True,
		)
		actual = rows[0]["name"] if rows else None
	if not actual:
		raise ValueError(f"DocType '{doctype}' does not exist. Create it first.")
	doctype = actual

	created = []
	for record in args["records"]:
		doc_data = dict(record)
		doc_data["doctype"] = doctype
		doc = frappe.get_doc(doc_data)
		try:
			doc.insert(ignore_permissions=True)
		except frappe.exceptions.MandatoryError as exc:
			# Extract the field name from "[DocType, name]: fieldname"
			raw = str(exc)
			field = raw.split(":")[-1].strip() if ":" in raw else raw
			raise ValueError(
				f"Missing mandatory field '{field}' in {doctype}. "
				f"Include it in every record."
			) from exc
		created.append(doc.name)

	frappe.db.commit()
	return {
		"name":    ", ".join(created),
		"doctype": doctype,
		"label":   f"{len(created)} record(s) created",
		"target":  doctype,
		"names":   created,   # kept for rollback
	}


# ════════════════════════════════════════════════════════════════
# Change log helpers
# ════════════════════════════════════════════════════════════════

_CHANGE_TYPE_MAP = {
	"create_custom_field":  "Custom Field",
	"create_server_script": "Server Script",
	"create_client_script": "Client Script",
	"create_workflow":      "Workflow",
	"create_doctype":       "DocType",
	"create_documents":     "Documents",
}


def _log_change(tool_name, args, result):
	target = (
		args.get("doctype")
		or args.get("reference_doctype")
		or args.get("dt")
		or args.get("document_type")
		or args.get("name")    # for create_doctype the target IS the new doctype
		or ""
	)
	# Multi-record rollback stores a names list; single-record stores name string
	rollback = {
		"doctype": result.get("doctype"),
		"name":    result.get("name"),
	}
	if result.get("names"):
		rollback["names"] = result["names"]

	doc = frappe.get_doc({
		"doctype":          "AI Change Log",
		"user":             frappe.session.user,
		"change_type":      _CHANGE_TYPE_MAP.get(tool_name, tool_name),
		"change_type_raw":  tool_name,
		"target_doctype":   target,
		"change_name":      result.get("name", ""),
		"payload":          json.dumps(args, indent=2),
		"rollback_payload": json.dumps(rollback),
		"status":           "Applied",
		"applied_at":       frappe.utils.now(),
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def _delete_record(doctype, name, names=None):
	"""Delete one record (name) or multiple (names list)."""
	if not doctype:
		raise ValueError("Cannot rollback: no doctype in rollback info.")
	if names:
		for n in names:
			if frappe.db.exists(doctype, n):
				frappe.delete_doc(doctype, n, ignore_permissions=True, force=True)
	else:
		if not name:
			raise ValueError("Cannot rollback: no name in rollback info.")
		if not frappe.db.exists(doctype, name):
			raise ValueError(f"{doctype} '{name}' no longer exists.")
		frappe.delete_doc(doctype, name, ignore_permissions=True, force=True)
	frappe.clear_cache()


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════

def _err(msg):
	return {"reply": msg, "preview": None}
