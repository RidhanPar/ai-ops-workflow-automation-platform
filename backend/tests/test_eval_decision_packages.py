import json
import re
from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_provider import LLMResult
from evaluations import eval_decision_packages as risk_eval


def _perspectives_reply(system: str, prompt: dict) -> LLMResult:
    treatment = "mitigate" if prompt["impact"] * prompt["likelihood"] >= 6 else "accept"
    perspectives = [
        {
            "area": area,
            "key_concerns": [f"{area} exposure described in {prompt['risk_title']}"],
            "reviewer_questions": ["Which controls are already in place?"],
            "suggested_treatment": treatment,
            "confidence": 0.8,
        }
        for area in ("security", "compliance", "business")
    ]
    return LLMResult(text=json.dumps({"perspectives": perspectives}), input_tokens=120, output_tokens=80)


@pytest.mark.parametrize(
    ("case_set", "results_name"),
    [("golden", "risk_results_openai.json"), ("holdout", "risk_holdout_results_openai.json")],
)
def test_provider_path_uses_provider_output_and_writes_a_separate_file(tmp_path, monkeypatch, case_set, results_name):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-never-sent")
    provider = MagicMock()
    provider.source_label = "openai_structured_output"
    provider.complete_json.side_effect = _perspectives_reply

    with patch("app.services.decision_package.get_llm_provider", return_value=provider):
        exit_code = risk_eval.main(["--set", case_set, "--provider", "openai"], out_dir=tmp_path)

    assert exit_code == 0
    assert [p.name for p in tmp_path.iterdir()] == [results_name]
    results = json.loads((tmp_path / results_name).read_text(encoding="utf-8"))
    assert results["mode"] == "openai"
    complete = [case for case in results["cases"] if not case["needs_info"]]
    assert provider.complete_json.call_count == len(complete)
    assert {case["source"] for case in complete} == {"openai_structured_output"}
    assert results["metrics"]["provider_output_rate"]["value"] == 1.0
    assert results["metrics"]["schema_validity"]["value"] == 1.0
    assert results["metrics"]["decisions_without_human"]["hits"] == 0
    assert results["threshold_failures"] == []


def test_provider_path_requires_the_provider_api_key(tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    assert risk_eval.main(["--provider", "anthropic"], out_dir=tmp_path) == 2
    assert list(tmp_path.iterdir()) == []


def test_golden_set_covers_the_required_case_types():
    cases = json.loads(risk_eval.GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]
    past_keys = {d["key"] for d in json.loads(risk_eval.PAST_DECISIONS_PATH.read_text(encoding="utf-8"))["decisions"]}

    assert len(cases) >= 25
    assert len({case["id"] for case in cases}) == len(cases)
    assert sum(case.get("injection_field") == "description" for case in cases) >= 3
    expected_past = [case["expected_similar_past"] for case in cases if case.get("expected_similar_past")]
    assert len(expected_past) >= 6
    assert set(expected_past) <= past_keys
    # With 3 or fewer decided risks every one of them lands in the top 3, so the hit rate would be meaningless.
    assert len(past_keys) > 3
    assert {case.get("level") for case in cases if not case["expected_needs_info"]} == {"clear", "borderline"}
    for case in cases:
        if case["expected_needs_info"]:
            assert case["expected_gaps"]
        else:
            assert case["expected_treatment"] in risk_eval.TREATMENTS


def test_holdout_set_covers_every_prompt_field_and_ordinary_trigger_words():
    cases = json.loads(risk_eval.HOLDOUT_PATH.read_text(encoding="utf-8"))["cases"]
    golden_ids = {c["id"] for c in json.loads(risk_eval.GOLDEN_PATH.read_text(encoding="utf-8"))["cases"]}
    past_keys = {d["key"] for d in json.loads(risk_eval.PAST_DECISIONS_PATH.read_text(encoding="utf-8"))["decisions"]}
    fields = ("title", "description", "proposed_mitigation", "business_unit", "owner")

    injections = [case for case in cases if case.get("injection_field")]
    assert len(injections) >= 8
    assert {case["injection_field"] for case in injections} == set(fields)
    clean_with_trigger_words = [
        case
        for case in cases
        if not case.get("injection_field")
        and re.search(r"bypass|overrid|ignor|instruction", " ".join(str(case.get(f) or "") for f in fields), re.IGNORECASE)
    ]
    assert len(clean_with_trigger_words) >= 8
    expected_past = [case["expected_similar_past"] for case in cases if case.get("expected_similar_past")]
    assert len(expected_past) >= 4
    assert set(expected_past) <= past_keys
    assert not {case["id"] for case in cases} & golden_ids
