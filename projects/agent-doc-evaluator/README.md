# Agent Doc Evaluator

Deterministic scoring harness for network documentation Q&A agent responses. Built to support Cursor-driven agent evaluation workflows (completeness, CLI validity, version awareness, cross-platform reasoning).

## Install

```bash
cd projects/agent-doc-evaluator
uv sync
```

## Run a suite

```bash
uv run agent-doc-eval run --suite suites/network_basics.json
```

Score one answer:

```bash
uv run agent-doc-eval score "Use show version on IOS-XE 17.09. Compared to Arista EOS, syntax differs."
```

## Rubric dimensions

| Dimension | What it approximates |
|-----------|----------------------|
| documentation_accuracy | Penalizes obvious guessing language |
| command_validity | Rewards CLI-like tokens when relevant |
| completeness | Length-based coverage heuristic |
| hallucination_resistance | Rewards citing missing/unclear docs |
| version_awareness | Detects version/release markers |
| cross_doc_reasoning | Detects cross-platform comparison language |
| clarity | Sentence structure and brevity |

Replace heuristics with model-graded or human review for production benchmarking.
