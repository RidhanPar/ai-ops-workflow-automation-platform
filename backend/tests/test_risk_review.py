"""Tests for the risk review workflow: RBAC, package generation, assessments, decisions."""
from unittest.mock import MagicMock, patch

import pytest

from app.db import SessionLocal
from app.models import AuditEvent
from app.services.llm_provider import LLMProviderError

# ---------------------------------------------------------------------------
# Helpers and fixtures
# ---------------------------------------------------------------------------

_COMPLETE_RISK = {
    "title": "SQL injection in public-facing search endpoint",
    "description": "The search API does not parameterize inputs, allowing an attacker to read or modify database contents.",
    "business_unit": "Engineering",
    "owner": "security-lead",
    "impact": 4,
    "likelihood": 3,
    "proposed_mitigation": "Parameterize all database queries and add integration tests to the CI pipeline.",
}

_INCOMPLETE_RISK = {
    "title": "Risk item with no proposed mitigation plan",
    "description": "An incomplete risk item used to verify the needs_info branch does not trigger the LLM provider.",
    "business_unit": "Engineering",
    "owner": "team-lead",
    "impact": 3,
    "likelihood": 3,
}


@pytest.fixture()
def risk_item(client, operator_headers):
    response = client.post("/risks", json=_COMPLETE_RISK, headers=operator_headers)
    assert response.status_code == 201
    return response.json()


def _assessment(perspective: str, vote: str = "mitigate", comment: str | None = None) -> dict:
    return {
        "perspective": perspective,
        "vote": vote,
        "comment": comment or f"{perspective.capitalize()} review completed; the mitigation plan is sound.",
    }


def _add_two_assessments(client, operator_headers, viewer_headers, pkg_id: int) -> None:
    r1 = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("security"),
        headers=operator_headers,
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("compliance"),
        headers=viewer_headers,
    )
    assert r2.status_code == 201


# ---------------------------------------------------------------------------
# RBAC: who can create risk items
# ---------------------------------------------------------------------------


def test_viewer_cannot_create_risk(client, viewer_headers):
    response = client.post(
        "/risks",
        json={
            "title": "Viewer access test risk",
            "description": "Testing that viewers are refused write access to the risk endpoint.",
            "business_unit": "IT",
            "owner": "it-lead",
            "impact": 2,
            "likelihood": 2,
        },
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_operator_can_create_risk(client, operator_headers):
    response = client.post(
        "/risks",
        json={
            "title": "Operator risk creation test",
            "description": "Verifying that operators can create risk items via the API successfully.",
            "business_unit": "IT",
            "owner": "it-security-lead",
            "impact": 2,
            "likelihood": 2,
            "proposed_mitigation": "Apply the standard IT hardening checklist.",
        },
        headers=operator_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "draft"
    assert body["version"] == 1


# ---------------------------------------------------------------------------
# RBAC: who can generate packages
# ---------------------------------------------------------------------------


def test_viewer_cannot_generate_package(client, viewer_headers, risk_item):
    response = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": "viewer-test-key-0001"},
        headers=viewer_headers,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# RBAC: who can make decisions
# ---------------------------------------------------------------------------


def test_viewer_cannot_decide(client, viewer_headers, risk_item):
    response = client.post(
        f"/risks/{risk_item['id']}/decision",
        json={
            "decision": "accept",
            "rationale": "This rationale is long enough for the test case to pass.",
            "decision_package_id": 1,
            "version": risk_item["version"],
        },
        headers=viewer_headers,
    )
    assert response.status_code == 403


def test_operator_cannot_decide(client, operator_headers, risk_item):
    response = client.post(
        f"/risks/{risk_item['id']}/decision",
        json={
            "decision": "accept",
            "rationale": "This rationale is long enough for the test case to pass.",
            "decision_package_id": 1,
            "version": risk_item["version"],
        },
        headers=operator_headers,
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Package generation
# ---------------------------------------------------------------------------


def test_package_generated_for_complete_risk(client, operator_headers, risk_item):
    response = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": f"test-pkg-{risk_item['id']}-complete-001"},
        headers=operator_headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["risk_item_id"] == risk_item["id"]
    assert body["needs_info"] is False
    assert len(body["perspectives"]) == 3
    assert body["risk_score"] == risk_item["impact"] * risk_item["likelihood"]
    assert body["recommended_treatment"] in ("accept", "mitigate", "transfer", "avoid")
    areas = {p["area"] for p in body["perspectives"]}
    assert areas == {"security", "compliance", "business"}
    assert "source" in body
    assert isinstance(body["cited_knowledge_ids"], list)
    assert isinstance(body["cited_decision_ids"], list)


def test_package_status_transitions_to_in_review(client, operator_headers, risk_item):
    client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": f"test-pkg-{risk_item['id']}-status-001"},
        headers=operator_headers,
    )
    risk_response = client.get(f"/risks/{risk_item['id']}", headers=operator_headers)
    assert risk_response.json()["status"] == "in_review"


def test_idempotent_package_generation(client, operator_headers, risk_item):
    key = f"test-idempotent-{risk_item['id']}-001"
    r1 = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": key},
        headers=operator_headers,
    )
    r2 = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": key},
        headers=operator_headers,
    )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]


# ---------------------------------------------------------------------------
# needs_info branch
# ---------------------------------------------------------------------------


def test_needs_info_422_when_no_mitigation(client, operator_headers):
    r_create = client.post("/risks", json=_INCOMPLETE_RISK, headers=operator_headers)
    assert r_create.status_code == 201
    risk_id = r_create.json()["id"]

    r_pkg = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"no-mitigation-key-{risk_id}"},
        headers=operator_headers,
    )
    assert r_pkg.status_code == 422
    detail = r_pkg.json()["detail"]
    assert "gaps" in detail
    assert any("mitigation" in g for g in detail["gaps"])
    assert "package_id" in detail


def test_needs_info_does_not_advance_status(client, operator_headers):
    r_create = client.post("/risks", json=_INCOMPLETE_RISK, headers=operator_headers)
    risk_id = r_create.json()["id"]

    client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"incomplete-status-{risk_id}"},
        headers=operator_headers,
    )
    risk_response = client.get(f"/risks/{risk_id}", headers=operator_headers)
    assert risk_response.json()["status"] == "draft"


def test_needs_info_never_calls_provider(client, operator_headers):
    with patch("app.services.decision_package.get_llm_provider") as mock_get:
        r_create = client.post("/risks", json=_INCOMPLETE_RISK, headers=operator_headers)
        assert r_create.status_code == 201
        r_pkg = client.post(
            f"/risks/{r_create.json()['id']}/decision-package",
            json={"idempotency_key": f"ni-no-provider-{r_create.json()['id']}"},
            headers=operator_headers,
        )
    assert r_pkg.status_code == 422
    mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# Source tracking: LLM fallback paths
# ---------------------------------------------------------------------------


def test_perspectives_source_no_provider(client, operator_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Source tracking test: no provider configured",
            "description": "This risk verifies the source field is set to fallback_no_provider when no LLM key is present.",
            "business_unit": "Platform",
            "owner": "platform-lead",
            "impact": 2,
            "likelihood": 2,
            "proposed_mitigation": "Apply the standard hardening checklist and document residual risk.",
        },
        headers=operator_headers,
    )
    risk_id = r_create.json()["id"]
    r_pkg = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"source-no-provider-{risk_id}"},
        headers=operator_headers,
    )
    assert r_pkg.status_code == 200
    assert r_pkg.json()["source"] == "fallback_no_provider"


def test_perspectives_source_fallback_invalid_output(client, operator_headers):
    mock_result = MagicMock()
    mock_result.text = '{"wrong_key": []}'
    mock_result.input_tokens = 10
    mock_result.output_tokens = 5

    mock_provider = MagicMock()
    mock_provider.source_label = "openai_structured_output"
    mock_provider.complete_json.return_value = mock_result

    with patch("app.services.decision_package.get_llm_provider", return_value=mock_provider):
        r_create = client.post(
            "/risks",
            json={
                "title": "Source tracking test: invalid LLM output",
                "description": "This risk verifies the source field is fallback_invalid_output when the provider returns malformed JSON.",
                "business_unit": "Security",
                "owner": "security-lead",
                "impact": 3,
                "likelihood": 2,
                "proposed_mitigation": "Apply network segmentation and document residual risk in the risk register.",
            },
            headers=operator_headers,
        )
        assert r_create.status_code == 201
        r_pkg = client.post(
            f"/risks/{r_create.json()['id']}/decision-package",
            json={"idempotency_key": f"invalid-output-{r_create.json()['id']}"},
            headers=operator_headers,
        )

    assert r_pkg.status_code == 200
    body = r_pkg.json()
    assert body["source"] == "fallback_invalid_output"
    areas = {p["area"] for p in body["perspectives"]}
    assert areas == {"security", "compliance", "business"}


def test_perspectives_source_fallback_provider_failure(client, operator_headers):
    mock_provider = MagicMock()
    mock_provider.source_label = "openai_structured_output"
    mock_provider.complete_json.side_effect = LLMProviderError("simulated connection timeout")

    with patch("app.services.decision_package.get_llm_provider", return_value=mock_provider):
        r_create = client.post(
            "/risks",
            json={
                "title": "Source tracking test: provider failure",
                "description": "This risk verifies the source field is fallback_provider_failure when the LLM provider raises an error.",
                "business_unit": "Operations",
                "owner": "ops-manager",
                "impact": 3,
                "likelihood": 3,
                "proposed_mitigation": "Implement automated failover and document recovery procedures in the runbook.",
            },
            headers=operator_headers,
        )
        assert r_create.status_code == 201
        r_pkg = client.post(
            f"/risks/{r_create.json()['id']}/decision-package",
            json={"idempotency_key": f"provider-failure-{r_create.json()['id']}"},
            headers=operator_headers,
        )

    assert r_pkg.status_code == 200
    assert r_pkg.json()["source"] == "fallback_provider_failure"


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------


def test_add_assessment(client, operator_headers, risk_item):
    pkg_response = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": f"assess-test-{risk_item['id']}-001"},
        headers=operator_headers,
    )
    pkg_id = pkg_response.json()["id"]

    response = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("security"),
        headers=operator_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["vote"] == "mitigate"
    assert body["reviewer"] == "operator"
    assert body["perspective"] == "security"


def test_duplicate_assessment_returns_409(client, operator_headers, risk_item):
    pkg_response = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": f"dup-assess-{risk_item['id']}-001"},
        headers=operator_headers,
    )
    pkg_id = pkg_response.json()["id"]

    client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("security", comment="First assessment comment is long enough to pass validation."),
        headers=operator_headers,
    )
    response = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("compliance", comment="Second attempt by the same reviewer should be rejected here."),
        headers=operator_headers,
    )
    assert response.status_code == 409


def test_assessment_blocked_on_needs_info_package(client, operator_headers):
    r_create = client.post("/risks", json=_INCOMPLETE_RISK, headers=operator_headers)
    risk_id = r_create.json()["id"]

    r_pkg = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"ni-assess-block-{risk_id}"},
        headers=operator_headers,
    )
    assert r_pkg.status_code == 422
    pkg_id = r_pkg.json()["detail"]["package_id"]

    response = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("security"),
        headers=operator_headers,
    )
    assert response.status_code == 422


def test_assessment_blocked_on_decided_risk(client, operator_headers, viewer_headers, manager_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Risk for decided-block assessment test",
            "description": "A full decided risk used to verify that assessments are rejected after a decision is made.",
            "business_unit": "Engineering",
            "owner": "lead-engineer",
            "impact": 2,
            "likelihood": 2,
            "proposed_mitigation": "Apply rate limiting and add to the quarterly security review schedule.",
        },
        headers=operator_headers,
    )
    assert r_create.status_code == 201
    risk_id = r_create.json()["id"]
    version = r_create.json()["version"]

    pkg_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"decided-block-{risk_id}"},
        headers=operator_headers,
    ).json()["id"]

    _add_two_assessments(client, operator_headers, viewer_headers, pkg_id)

    client.post(
        f"/risks/{risk_id}/decision",
        json={
            "decision": "accept",
            "rationale": "Risk score is low and the cost of mitigation exceeds the expected impact value.",
            "decision_package_id": pkg_id,
            "version": version,
        },
        headers=manager_headers,
    )

    response = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("business", comment="Attempted post-decision assessment that should be blocked here."),
        headers=manager_headers,
    )
    assert response.status_code == 409


def test_assessment_blocked_on_non_latest_package(client, operator_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Risk for non-latest-package assessment test",
            "description": "Two packages will be created for this risk to verify that only the latest package accepts assessments.",
            "business_unit": "Compliance",
            "owner": "compliance-officer",
            "impact": 2,
            "likelihood": 3,
            "proposed_mitigation": "Review and document residual risk against the current compliance framework.",
        },
        headers=operator_headers,
    )
    risk_id = r_create.json()["id"]

    pkg1_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"non-latest-pkg1-{risk_id}"},
        headers=operator_headers,
    ).json()["id"]

    pkg2_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"non-latest-pkg2-{risk_id}"},
        headers=operator_headers,
    ).json()["id"]

    assert pkg2_id > pkg1_id

    response = client.post(
        f"/decision-packages/{pkg1_id}/assessments",
        json=_assessment("security", comment="Attempting to assess a stale package that is no longer the latest."),
        headers=operator_headers,
    )
    assert response.status_code == 409


# ---------------------------------------------------------------------------
# Decision rules: version check and 2-assessment minimum
# ---------------------------------------------------------------------------


def test_stale_version_rejected(client, manager_headers, risk_item):
    response = client.post(
        f"/risks/{risk_item['id']}/decision",
        json={
            "decision": "mitigate",
            "rationale": "This rationale is long enough to satisfy the minimum length requirement.",
            "decision_package_id": 9999,
            "version": risk_item["version"] + 50,
        },
        headers=manager_headers,
    )
    assert response.status_code == 409


def test_decision_requires_two_assessments(client, operator_headers, manager_headers, risk_item):
    pkg_id = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": f"one-assess-{risk_item['id']}-001"},
        headers=operator_headers,
    ).json()["id"]

    client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("security", comment="Only one assessment submitted; a second one is still required."),
        headers=operator_headers,
    )

    response = client.post(
        f"/risks/{risk_item['id']}/decision",
        json={
            "decision": "mitigate",
            "rationale": "This rationale is long enough to satisfy the minimum length requirement.",
            "decision_package_id": pkg_id,
            "version": risk_item["version"],
        },
        headers=manager_headers,
    )
    assert response.status_code == 422


def test_separation_of_duties_422(client, operator_headers, manager_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Risk for separation-of-duties test",
            "description": "A risk item used to verify that the deciding manager cannot count their own assessment toward the required two.",
            "business_unit": "Compliance",
            "owner": "compliance-officer",
            "impact": 2,
            "likelihood": 3,
            "proposed_mitigation": "Implement automated compliance checks and schedule a quarterly review.",
        },
        headers=operator_headers,
    )
    assert r_create.status_code == 201
    risk_id = r_create.json()["id"]
    version = r_create.json()["version"]

    pkg_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"sep-duties-{risk_id}"},
        headers=operator_headers,
    ).json()["id"]

    client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("security"),
        headers=operator_headers,
    )
    client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json=_assessment("compliance"),
        headers=manager_headers,
    )

    response = client.post(
        f"/risks/{risk_id}/decision",
        json={
            "decision": "mitigate",
            "rationale": "This rationale is long enough to satisfy the minimum length requirement.",
            "decision_package_id": pkg_id,
            "version": version,
        },
        headers=manager_headers,
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "deciding manager" in detail["message"].lower() or "1 qualifying" in detail["message"]
    assert detail["deciding_user"] == "manager"


def test_decision_rejects_non_latest_package(client, operator_headers, viewer_headers, manager_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Risk for non-latest-package decision test",
            "description": "Two packages are generated so the first becomes stale and the decision endpoint must reject it.",
            "business_unit": "Platform",
            "owner": "platform-lead",
            "impact": 2,
            "likelihood": 2,
            "proposed_mitigation": "Add automated scanning to the CI pipeline and document residual exposure.",
        },
        headers=operator_headers,
    )
    assert r_create.status_code == 201
    risk_id = r_create.json()["id"]
    version = r_create.json()["version"]

    pkg1_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"stale-pkg1-{risk_id}"},
        headers=operator_headers,
    ).json()["id"]

    pkg2_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"stale-pkg2-{risk_id}"},
        headers=operator_headers,
    ).json()["id"]

    _add_two_assessments(client, operator_headers, viewer_headers, pkg2_id)

    response = client.post(
        f"/risks/{risk_id}/decision",
        json={
            "decision": "mitigate",
            "rationale": "This rationale is long enough to satisfy the minimum length requirement.",
            "decision_package_id": pkg1_id,
            "version": version,
        },
        headers=manager_headers,
    )
    assert response.status_code == 409


def test_manager_can_make_decision(client, operator_headers, viewer_headers, manager_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Risk for the full decision workflow test",
            "description": "A complete risk item used to exercise the entire review and decision workflow end-to-end.",
            "business_unit": "Engineering",
            "owner": "lead-engineer",
            "impact": 3,
            "likelihood": 3,
            "proposed_mitigation": "Implement automated security scanning as a required step in the CI pipeline.",
        },
        headers=operator_headers,
    )
    assert r_create.status_code == 201
    risk = r_create.json()
    risk_id = risk["id"]
    version = risk["version"]

    pkg_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"decide-flow-{risk_id}-001"},
        headers=operator_headers,
    ).json()["id"]

    _add_two_assessments(client, operator_headers, viewer_headers, pkg_id)

    response = client.post(
        f"/risks/{risk_id}/decision",
        json={
            "decision": "mitigate",
            "rationale": "Risk is confirmed and the proposed mitigation controls are appropriate and cost-effective.",
            "decision_package_id": pkg_id,
            "version": version,
        },
        headers=manager_headers,
    )
    assert response.status_code == 201
    assert response.json()["decision"] == "mitigate"
    assert response.json()["decided_by"] == "manager"

    risk_response = client.get(f"/risks/{risk_id}", headers=operator_headers)
    assert risk_response.json()["status"] == "decided"
    assert risk_response.json()["version"] == version + 1


# ---------------------------------------------------------------------------
# Past decision ranking
# ---------------------------------------------------------------------------


def test_past_decision_ranking_most_similar(client, operator_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "SQL injection risk for past-decision ranking test",
            "description": "A risk item similar to existing decided risks to verify that past_decisions are ranked by similarity score descending.",
            "business_unit": "Engineering",
            "owner": "security-lead",
            "impact": 4,
            "likelihood": 3,
            "proposed_mitigation": "Parameterize all queries and enforce input validation at the API boundary.",
        },
        headers=operator_headers,
    )
    assert r_create.status_code == 201
    risk_id = r_create.json()["id"]

    r_pkg = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"ranking-test-{risk_id}"},
        headers=operator_headers,
    )
    assert r_pkg.status_code == 200
    past = r_pkg.json()["past_decisions"]
    for i in range(len(past) - 1):
        assert past[i]["similarity_score"] >= past[i + 1]["similarity_score"], (
            f"past_decisions[{i}].similarity_score={past[i]['similarity_score']} < "
            f"past_decisions[{i+1}].similarity_score={past[i+1]['similarity_score']}"
        )


# ---------------------------------------------------------------------------
# Audit events
# ---------------------------------------------------------------------------


def test_audit_events_written_for_risk_create(client, operator_headers, database):
    response = client.post(
        "/risks",
        json={
            "title": "Audit event test risk item",
            "description": "Risk item created specifically to verify that audit events are recorded correctly.",
            "business_unit": "Compliance",
            "owner": "compliance-officer",
            "impact": 2,
            "likelihood": 2,
            "proposed_mitigation": "Review controls and document residual risk acceptance.",
        },
        headers=operator_headers,
    )
    assert response.status_code == 201
    risk_id = response.json()["id"]

    db = SessionLocal()
    try:
        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.resource_type == "risk_item",
                AuditEvent.resource_id == str(risk_id),
            )
            .all()
        )
        assert any(e.action == "risk.created" for e in events)
    finally:
        db.close()


def test_audit_events_written_for_decision(client, operator_headers, viewer_headers, manager_headers, database):
    r_create = client.post(
        "/risks",
        json={
            "title": "Audit decision trace test risk",
            "description": "Used to confirm that a risk decision records an audit event correctly in the database.",
            "business_unit": "IT",
            "owner": "it-lead",
            "impact": 2,
            "likelihood": 2,
            "proposed_mitigation": "Apply network segmentation and document residual risk.",
        },
        headers=operator_headers,
    )
    risk = r_create.json()
    risk_id = risk["id"]

    pkg_id = client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"audit-decision-{risk_id}-001"},
        headers=operator_headers,
    ).json()["id"]

    _add_two_assessments(client, operator_headers, viewer_headers, pkg_id)

    client.post(
        f"/risks/{risk_id}/decision",
        json={
            "decision": "accept",
            "rationale": "Risk score is low and the cost of mitigation exceeds the expected impact.",
            "decision_package_id": pkg_id,
            "version": risk["version"],
        },
        headers=manager_headers,
    )

    db = SessionLocal()
    try:
        events = (
            db.query(AuditEvent)
            .filter(
                AuditEvent.resource_type == "risk_item",
                AuditEvent.resource_id == str(risk_id),
            )
            .all()
        )
        actions = {e.action for e in events}
        assert "risk.decision_made" in actions
    finally:
        db.close()
