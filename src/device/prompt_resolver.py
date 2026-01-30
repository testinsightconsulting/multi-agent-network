"""Resolve prompt handlers using catalog + RAG + web search."""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.knowledge.rag_engine import RAGEngine
from src.knowledge.web_search import WebSearch


_PROMPT_PATTERNS = [
    (re.compile(r"\[y/n\]", re.IGNORECASE), "y\n"),
    (re.compile(r"\(y/n\)", re.IGNORECASE), "y\n"),
    (re.compile(r"\[yes/no\]", re.IGNORECASE), "yes\n"),
    (re.compile(r"\(yes/no\)", re.IGNORECASE), "yes\n"),
    (re.compile(r"\[confirm\]", re.IGNORECASE), "\n"),
    (re.compile(r"\(press RETURN\)", re.IGNORECASE), "\n"),
    (re.compile(r"press RETURN", re.IGNORECASE), "\n"),
    (re.compile(r"Press Enter to continue", re.IGNORECASE), "\n"),
    (re.compile(r"Are you sure.*\?", re.IGNORECASE), "yes\n"),
    (re.compile(r"Continue\?.*\[yes/no\]", re.IGNORECASE), "yes\n"),
    (re.compile(r"Continue\?.*\[y/n\]", re.IGNORECASE), "y\n"),
]


class PromptResolver:
    """Suggest prompt handlers using catalog + RAG + web search."""

    def __init__(
        self,
        device_type: str,
        model: str,
        os_version: str,
        rag_engine: Optional[RAGEngine],
        web_search: Optional[WebSearch],
    ):
        self.device_type = device_type
        self.model = model
        self.os_version = os_version
        self.rag_engine = rag_engine
        self.web_search = web_search

    def suggest_handlers(self, text: str, max_handlers: int = 5) -> Dict[str, List[dict]]:
        """Suggest prompt handlers by scanning text and known patterns."""
        handlers: List[dict] = []
        sources: List[str] = []

        handlers += self._extract_from_text(text)
        if handlers:
            sources.append("input")

        if not handlers and self.rag_engine:
            rag_query = f"prompt examples confirmation prompts {self.device_type} {self.model} {self.os_version}".strip()
            rag_text = self.rag_engine.query(rag_query, device_type=self.device_type)
            handlers += self._extract_from_text(rag_text)
            if handlers:
                sources.append("rag")

        if not handlers and self.web_search:
            web_query = f"{self.device_type} cli confirmation prompt [y/n] examples".strip()
            web_text = self.web_search.search(web_query)
            handlers += self._extract_from_text(web_text)
            if handlers:
                sources.append("web")

        # Deduplicate by pattern
        unique = []
        seen = set()
        for h in handlers:
            key = h.get("pattern")
            if key and key not in seen:
                unique.append(h)
                seen.add(key)
        return {"handlers": unique[:max_handlers], "sources": sources}

    def _extract_from_text(self, text: Optional[str]) -> List[dict]:
        if not text:
            return []
        handlers = []
        for pattern, response in _PROMPT_PATTERNS:
            if pattern.search(text):
                handlers.append({"pattern": pattern.pattern, "response": response})
        # Also look for explicit lines like "Do you want to continue? [y/n]"
        for line in text.splitlines():
            if "[" in line and "]" in line and "y/n" in line.lower():
                handlers.append({"pattern": re.escape(line.strip()), "response": "y\n"})
        return handlers
