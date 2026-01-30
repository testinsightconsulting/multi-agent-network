"""Resolve device commands for a question using catalog + RAG + web search."""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.knowledge.rag_engine import RAGEngine
from src.knowledge.web_search import WebSearch


_SHOW_PATTERN = re.compile(r"^(show|display|get)\b", re.IGNORECASE)

_KEYWORD_TO_KEYS: List[Tuple[str, List[str]]] = [
    ("bgp", ["show_bgp"]),
    ("ospf", ["show_ospf"]),
    ("interface", ["show_interfaces"]),
    ("interfaces", ["show_interfaces"]),
    ("config", ["show_config"]),
    ("configuration", ["show_config"]),
    ("version", ["show_version"]),
    ("vlan", ["show_vlans"]),
    ("stp", ["show_stp"]),
    ("platform", ["show_platform"]),
    ("status", ["show_status"]),
]


class CommandResolver:
    """Resolve candidate commands for a question."""

    def __init__(
        self,
        device_type: str,
        model: str,
        os_version: str,
        commands: Dict[str, str],
        rag_engine: Optional[RAGEngine],
        web_search: Optional[WebSearch],
    ):
        self.device_type = device_type
        self.model = model
        self.os_version = os_version
        self.commands = commands or {}
        self.rag_engine = rag_engine
        self.web_search = web_search

    def suggest_commands(self, question: str, max_commands: int = 3) -> Dict[str, List[str]]:
        """Return candidate commands and a short list of sources used."""
        candidates: List[str] = []
        sources: List[str] = []

        lower = (question or "").lower()
        for keyword, keys in _KEYWORD_TO_KEYS:
            if keyword in lower:
                for key in keys:
                    cmd = self.commands.get(key)
                    if cmd:
                        candidates.append(cmd)
                if candidates:
                    sources.append("catalog")
                    break

        # If nothing matched by keyword, offer a small generic subset
        if not candidates:
            for key in ("show_config", "show_interfaces", "show_bgp"):
                cmd = self.commands.get(key)
                if cmd:
                    candidates.append(cmd)
            if candidates:
                sources.append("catalog")

        # If still empty, try RAG and web search to suggest commands
        if not candidates and self.rag_engine:
            rag_query = f"{question} show commands {self.device_type} {self.model} {self.os_version}".strip()
            rag_text = self.rag_engine.query(rag_query, device_type=self.device_type)
            candidates += self._extract_commands(rag_text)
            if candidates:
                sources.append("rag")

        if not candidates and self.web_search:
            web_query = f"{question} show commands {self.device_type} {self.model} {self.os_version}".strip()
            web_text = self.web_search.search(web_query)
            candidates += self._extract_commands(web_text)
            if candidates:
                sources.append("web")

        # Deduplicate and cap
        unique = []
        seen = set()
        for cmd in candidates:
            if cmd and cmd not in seen:
                unique.append(cmd)
                seen.add(cmd)
        return {"commands": unique[:max_commands], "sources": sources}

    def _extract_commands(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        commands: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if _SHOW_PATTERN.match(line):
                commands.append(line)
        return commands
