from app.services.agent import _fallback_analysis
from evaluations.eval_ai_assistant import TEST_CASES, _fallback
from evaluations.run_evaluations import run


def test_golden_evaluation_quality_gates():
    result = run()
    assert result["routing_accuracy"] >= 0.8
    assert result["priority_accuracy"] >= 0.8
    assert result["schema_validity"] == 1
    assert result["prompt_injection_detection"] is True
    assert result["average_latency_ms"] < 50


def test_eval_inline_fallback_stays_in_sync_with_agent_fallback():
    """Drift between the inlined copy in eval_ai_assistant and _fallback_analysis in agent.py
    fails CI before it reaches production, so the two never diverge silently."""
    for case in TEST_CASES:
        inp = case["input"]
        title, description, channel = inp["title"], inp["description"], inp.get("channel", "email")
        eval_result = _fallback(title, description, channel)
        agent_result = _fallback_analysis(title, description, channel)
        assert eval_result.category == agent_result.category, (
            f"Case {case['name']}: category mismatch "
            f"eval={eval_result.category!r} agent={agent_result.category!r}"
        )
        assert eval_result.recommended_priority == agent_result.recommended_priority, (
            f"Case {case['name']}: priority mismatch "
            f"eval={eval_result.recommended_priority!r} agent={agent_result.recommended_priority!r}"
        )
        assert eval_result.recommended_team == agent_result.recommended_team, (
            f"Case {case['name']}: team mismatch "
            f"eval={eval_result.recommended_team!r} agent={agent_result.recommended_team!r}"
        )
