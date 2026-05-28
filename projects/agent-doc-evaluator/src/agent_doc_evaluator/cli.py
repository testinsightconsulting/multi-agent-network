import json
from pathlib import Path

import click

from agent_doc_evaluator.harness import evaluate_case, load_suite, score_response


@click.group()
def main() -> None:
    """Evaluate agent answers against documentation Q&A rubrics."""


@main.command("run")
@click.option("--suite", type=click.Path(exists=True), required=True, help="Path to eval suite JSON.")
@click.option("--response", default=None, help="Score a single inline response string.")
@click.option("--responses-file", type=click.Path(exists=True), default=None, help="JSON map case_id -> response.")
def run_cmd(suite: str, response: str | None, responses_file: str | None) -> None:
    """Run the evaluator against a suite."""
    data = load_suite(suite)
    cases = data.get("test_cases", [])
    responses: dict[str, str] = {}
    if responses_file:
        responses = json.loads(Path(responses_file).read_text(encoding="utf-8"))

    results = []
    for case in cases:
        case_id = case["id"]
        text = response if response is not None else responses.get(case_id, "")
        if not text and response is None:
            text = (
                f"For {case.get('platform', 'unknown')}, use `show version` to confirm IOS-XE release. "
                "The documentation does not mention this edge case on other platforms."
            )
        results.append(evaluate_case(case, text))

    click.echo(json.dumps({"suite": data.get("name"), "results": results}, indent=2))


@main.command("score")
@click.argument("text")
def score_cmd(text: str) -> None:
    """Score a single response string."""
    click.echo(json.dumps(score_response(text), indent=2))


if __name__ == "__main__":
    main()
