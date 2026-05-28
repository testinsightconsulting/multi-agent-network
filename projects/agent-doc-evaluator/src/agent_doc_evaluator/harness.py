"""Rule-based scorer for agent answers about network platform documentation."""
import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_SUITE = Path(__file__).resolve().parent.parent.parent / "suites" / "network_basics.json"


def load_suite(path: Path | str = DEFAULT_SUITE) -> Dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _word_count(text: str) -> int:
    return len(text.split())


def _has_cli_tokens(text_lower: str) -> bool:
    cli_markers = [
        "show ",
        "configure ",
        "router ",
        "interface ",
        "set ",
        "get ",
        "commit",
        "display ",
    ]
    return any(marker in text_lower for marker in cli_markers)


def _has_version_markers(text_lower: str) -> bool:
    markers = ["version", "release", "esxi 8", "ios-xe", "eos ", "edgeos", "fortios"]
    return any(marker in text_lower for marker in markers)


def _has_cross_platform_markers(text_lower: str) -> bool:
    markers = [
        "on the other hand",
        "by contrast",
        "compared to",
        "in contrast",
        "across platforms",
        "for esxi",
        "for cisco",
        "for arista",
        "for fortinet",
        "for vyos",
        "for pfsense",
    ]
    return any(marker in text_lower for marker in markers)


def _score_completeness(word_count: int) -> int:
    if word_count < 8:
        return 1
    if word_count < 25:
        return 3
    if word_count < 80:
        return 4
    return 5


def _score_clarity(response: str) -> int:
    sentences = [s for s in response.replace("?", ".").split(".") if s.strip()]
    word_count = _word_count(response)
    if word_count == 0:
        return 0
    if len(sentences) == 1 and word_count > 40:
        return 2
    if len(sentences) >= 2 and word_count <= 60:
        return 4
    return 3


def _score_hallucination_resistance(text_lower: str) -> int:
    cautious_markers = [
        "not documented",
        "documentation does not mention",
        "cannot confirm from the documentation",
        "the documentation is unclear",
    ]
    if any(marker in text_lower for marker in cautious_markers):
        return 4
    return 3


def _score_documentation_accuracy(text_lower: str) -> int:
    if "guess" in text_lower or "probably" in text_lower:
        return 2
    return 3


def _score_command_validity(text_lower: str) -> int:
    if not _has_cli_tokens(text_lower):
        return 3
    return 4


def _score_version_awareness(text_lower: str) -> int:
    if _has_version_markers(text_lower):
        return 4
    return 2


def _score_cross_doc_reasoning(text_lower: str) -> int:
    if _has_cross_platform_markers(text_lower):
        return 4
    return 2


def score_response(response: str, rubric_weights: Dict[str, float] | None = None) -> Dict[str, Any]:
    """Score an agent response using lightweight deterministic heuristics."""
    response = response or ""
    text_lower = response.lower()
    word_count = _word_count(response)

    dimensions = [
        "documentation_accuracy",
        "command_validity",
        "completeness",
        "hallucination_resistance",
        "version_awareness",
        "cross_doc_reasoning",
        "clarity",
    ]
    weights = rubric_weights or {name: 1.0 for name in dimensions}

    scores: Dict[str, int] = {
        "documentation_accuracy": _score_documentation_accuracy(text_lower),
        "command_validity": _score_command_validity(text_lower),
        "completeness": _score_completeness(word_count),
        "hallucination_resistance": _score_hallucination_resistance(text_lower),
        "version_awareness": _score_version_awareness(text_lower),
        "cross_doc_reasoning": _score_cross_doc_reasoning(text_lower),
        "clarity": _score_clarity(response),
    }

    weighted_total = sum(scores[d] * weights.get(d, 1.0) for d in dimensions)
    weight_sum = sum(weights.get(d, 1.0) for d in dimensions)

    return {
        "scores": scores,
        "weights": weights,
        "weighted_average": round(weighted_total / weight_sum, 2) if weight_sum else 0,
        "notes": (
            "Scores use rule-based heuristics. Replace with model-graded or human review for production."
        ),
    }


def evaluate_case(case: Dict[str, Any], response: str) -> Dict[str, Any]:
    """Score a response for a single test case from a suite."""
    rubric = case.get("rubric_weights") or case.get("rubric") or {}
    result = score_response(response, rubric_weights=rubric if isinstance(rubric, dict) else None)
    return {
        "case_id": case.get("id"),
        "platform": case.get("platform"),
        "category": case.get("category"),
        **result,
    }
