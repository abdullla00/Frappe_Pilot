"""Plain text extraction."""

import hashlib


class ExtractedText:
	def __init__(self, text: str, title: str = "", source_hash: str = ""):
		self.text = text or ""
		self.title = title
		self.source_hash = source_hash or hashlib.sha256(self.text.encode()).hexdigest()


class TextExtractor:
	def extract_from_text(self, text: str, title: str = "Text Input") -> ExtractedText:
		return ExtractedText(text=text, title=title)

	def extract_from_file(self, file_url: str) -> ExtractedText:
		import frappe

		content = frappe.get_doc("File", {"file_url": file_url})
		path = content.get_full_path()
		with open(path, encoding="utf-8", errors="ignore") as handle:
			text = handle.read()
		return ExtractedText(text=text, title=content.file_name or file_url)
