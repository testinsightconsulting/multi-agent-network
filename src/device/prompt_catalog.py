"""Prompt handling catalog per vendor (regex -> response)."""
from typing import Dict, List


DEFAULT_PROMPT_REGEX = r"[>#\$]\s*$"

PROMPT_HANDLERS: Dict[str, List[dict]] = {
    "generic": [
        {"pattern": r"--More--", "response": " "},
        {"pattern": r"\[confirm\]", "response": "\n"},
        {"pattern": r"\[y/n\]", "response": "y\n"},
        {"pattern": r"\(y/n\)", "response": "y\n"},
        {"pattern": r"\[yes/no\]", "response": "yes\n"},
        {"pattern": r"Are you sure.*\?", "response": "yes\n"},
        {"pattern": r"Press any key to continue", "response": "\n"},
    ],
    "cisco": [
        {"pattern": r"--More--", "response": " "},
        {"pattern": r"\[confirm\]", "response": "\n"},
        {"pattern": r"\[y/n\]", "response": "y\n"},
        {"pattern": r"Continue\? \[yes/no\]:", "response": "yes\n"},
    ],
    "arista": [
        {"pattern": r"--More--", "response": " "},
        {"pattern": r"\[confirm\]", "response": "\n"},
        {"pattern": r"\[y/n\]", "response": "y\n"},
        {"pattern": r"Continue\? \[y/n\]:", "response": "y\n"},
    ],
    "juniper": [
        {"pattern": r"---\(more\)---", "response": " "},
        {"pattern": r"\[yes,no\]", "response": "yes\n"},
        {"pattern": r"Do you want to continue\?", "response": "yes\n"},
    ],
    "spirent": [
        {"pattern": r"\[confirm\]", "response": "\n"},
    ],
    "vyos": [
        {"pattern": r"\(press RETURN\)", "response": "\n"},
        {"pattern": r"press RETURN", "response": "\n"},
        {"pattern": r"\[confirm\]", "response": "\n"},
        {"pattern": r"\[y/n\]", "response": "y\n"},
    ],
}


def get_prompt_regex_for_device(device_type: str) -> str:
    key = (device_type or "generic").strip().lower()
    return DEFAULT_PROMPT_REGEX


def get_prompt_handlers_for_device(device_type: str) -> List[dict]:
    key = (device_type or "generic").strip().lower()
    handlers = PROMPT_HANDLERS.get(key, PROMPT_HANDLERS["generic"])
    return [dict(h) for h in handlers]
