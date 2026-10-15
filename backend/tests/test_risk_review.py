"""Tests for the risk review workflow: RBAC, package generation, assessments, decisions."""
import pytest

from app.db import SessionLocal
from app.models import AuditEvent

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


@pytest.fixture()
def risk_item(client, operator_headers):
    response = client.post("/risks", json=_COMPLETE_RISK, headers=operator_headers)
    assert response.status_code == 201
    return response.json()


def _add_two_assessments(client, operator_headers, manager_headers, pkg_id: int) -> None:
    r1 = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json={"vote": "mitigate", "comment": "Risk is confirmed; mitigation approach is technically sound."},
        headers=operator_headers,
    )
    assert r1.status_code == 201
    r2 = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json={"vote": "mitigate", "comment": "Compliance risk is material; mitigation aligns with policy."},
        headers=manager_headers,
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
# needs_info branch (no LLM called for completeness gaps)
# ---------------------------------------------------------------------------


def test_needs_info_422_when_no_mitigation(client, operator_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Risk item with no proposed mitigation",
            "description": "This risk item intentionally has no mitigation plan to trigger the needs_info branch.",
            "business_unit": "Engineering",
            "owner": "team-lead",
            "impact": 3,
            "likelihood": 3,
        },
        headers=operator_headers,
    )
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


def test_needs_info_does_not_advance_status(client, operator_headers):
    r_create = client.post(
        "/risks",
        json={
            "title": "Incomplete risk for status check",
            "description": "Verifying that an incomplete risk stays in draft when needs_info fires.",
            "business_unit": "Engineering",
            "owner": "team-lead",
            "impact": 2,
            "likelihood": 2,
        },
        headers=operator_headers,
    )
    risk_id = r_create.json()["id"]

    client.post(
        f"/risks/{risk_id}/decision-package",
        json={"idempotency_key": f"incomplete-status-{risk_id}"},
        headers=operator_headers,
    )
    risk_response = client.get(f"/risks/{risk_id}", headers=operator_headers)
    assert risk_response.json()["status"] == "draft"


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
        json={"vote": "mitigate", "comment": "This risk needs mitigation based on the technical review findings."},
        headers=operator_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["vote"] == "mitigate"
    assert body["reviewer"] == "operator"


def test_duplicate_assessment_returns_409(client, operator_headers, risk_item):
    pkg_response = client.post(
        f"/risks/{risk_item['id']}/decision-package",
        json={"idempotency_key": f"dup-assess-{risk_item['id']}-001"},
        headers=operator_headers,
    )
    pkg_id = pkg_response.json()["id"]

    client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json={"vote": "mitigate", "comment": "First assessment comment is long enough to pass validation."},
        headers=operator_headers,
    )
    response = client.post(
        f"/decision-packages/{pkg_id}/assessments",
        json={"vote": "accept", "comment": "Second attempt by the same reviewer should be rejected."},
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
        json={"vote": "mitigate", "comment": "Only one assessment submitted; a second one is still required."},
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


def test_manager_can_make_decision(client, operator_headers, manager_headers):
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

    _add_two_assessments(client, operator_headers, manager_headers, pkg_id)

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


def test_audit_events_written_for_decision(client, operator_headers, manager_headers, database):
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

    _add_two_assessments(client, operator_headers, manager_headers, pkg_id)

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
