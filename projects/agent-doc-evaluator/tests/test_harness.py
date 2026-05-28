from agent_doc_evaluator.harness import evaluate_case, load_suite, score_response


def test_score_response_includes_dimensions():
    result = score_response("Use `show version` on IOS-XE 17.09. Compared to Arista EOS, the syntax differs.")
    assert "scores" in result
    assert result["scores"]["command_validity"] >= 3
    assert result["scores"]["version_awareness"] >= 3
    assert result["weighted_average"] > 0


def test_evaluate_case_from_suite():
    suite = load_suite()
    case = suite["test_cases"][0]
    result = evaluate_case(case, "Run show version to verify IOS-XE release 17.09.")
    assert result["case_id"] == "cisco_ios_xe_version"
    assert result["scores"]["command_validity"] >= 3


def test_hallucination_cautious_answer_scores_higher():
    cautious = score_response("The documentation does not mention ultra-fast-converge-mode on EOS.")
    guessing = score_response("Probably ultra-fast-converge-mode is enabled by default.")
    assert cautious["scores"]["hallucination_resistance"] >= guessing["scores"]["hallucination_resistance"]
