from evaluations.run_evaluations import run


def test_golden_evaluation_quality_gates():
    result = run()
    assert result["routing_accuracy"] >= 0.8
    assert result["priority_accuracy"] >= 0.8
    assert result["schema_validity"] == 1
    assert result["prompt_injection_detection"] is True
    assert result["average_latency_ms"] < 50
