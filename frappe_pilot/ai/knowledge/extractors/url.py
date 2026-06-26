"""URL text extraction (simplified)."""

import hashlib

import requests

from .text import ExtractedText


class URLExtractor:
	def extract(self, url: str) -> ExtractedText:
		response = requests.get(url, timeout=30)
		response.raise_for_status()
		text = response.text
		return ExtractedText(
			text=text,
			title=url,
			source_hash=hashlib.sha256(text.encode()).hexdigest(),
		)
