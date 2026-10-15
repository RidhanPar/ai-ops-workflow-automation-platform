# Risk Review

This document explains how decision packages are built, why the AI recommends but never decides, how separation of duties is enforced, and the trade-offs involved. Every behaviour described here can be checked in `backend/app/services/decision_package.py` and `backend/app/routers/risks.py`.

## Decision Package Design

A decision package is what an operator gets back after asking the system to analyse a risk item. It puts everything a reviewer needs in one place before anyone votes.

The package is built by a LangGraph `StateGraph` in `backend/app/services/decision_package.py`:

1. **Completeness check.** The pipeline requires an owner, impact and likelihood between 1 and 5, a proposed mitigation, and a description of at least 20 characters. If anything is missing the graph ends here, the package is saved with `needs_info=true` and a list of gaps, and no LLM call is made. Assessments cannot be added to an incomplete package. The same step scans the title and description for five known injection phrases (`ignore previous`, `system prompt`, `reveal secret`, `developer message`, `bypass`) and records any match in `safety_flags`.

2. **Best practice retrieval.** The 3 closest knowledge base documents are attached as `best_practices`. On PostgreSQL this search uses pgvector. On SQLite it ranks the stored local embeddings in Python.

3. **Past decision retrieval.** Every decided risk is embedded with the deterministic local hashing function in `backend/app/services/knowledge.py`, ranked by cosine similarity against the new risk, and the top 3 are attached as `past_decisions` with their decision and rationale. This step runs in Python on every database and does not use pgvector.

4. **Perspective generation.** The provider-agnostic LLM layer returns security, compliance and business perspectives. Each has key concerns, reviewer questions, a suggested treatment and a confidence score. Reference documents and past decisions are passed inside an `untrusted_reference_data` block with an instruction not to follow anything written there. When no API key is set, or the provider fails or returns invalid output, deterministic fallback perspectives are used instead. The `source` field records which path produced the perspectives: `openai_structured_output`, `anthropic_messages`, `fallback_no_provider`, `fallback_invalid_output`, `fallback_provider_failure`, `fallback_unexpected_failure`, or `seed` for demo data.

5. **Assembly.** `risk_score` is impact × likelihood (1 to 25) and `recommended_treatment` is the most common suggested treatment across the three perspectives.

## Why the AI Recommends but Never Decides

Generating a package writes a `DecisionPackage` row, trace spans and a `risk.package_generated` audit event, and moves a draft risk to `in_review`. It never creates a `RiskDecision` row and never sets a risk to `decided`. The only code that does either is the `POST /risks/{id}/decision` handler, which needs a manager or admin and the checks described below. This is enforced by where the writes live in the application code, not by instructions to the model.

There are three reasons for this design.

**Accountability.** Accepting or treating an organisational risk has real consequences. The decision needs a named person who can be held to account if the risk materialises. A model output cannot fill that role.

**Auditability.** Each decision is stored as a `RiskDecision` row with the deciding user, the decision, the rationale and the package it was based on. The handler also writes a `risk.decision_made` audit event with the actor, trace ID, status before and after, and the new risk version. Model outputs are harder to audit: the same input can produce different outputs, and models change over time.

**Quality of judgement.** The model only sees the text it is given. Reviewers know things the model cannot: priorities, controls already in flight, budgets and regulatory history. The package structures that human judgement rather than replacing it.

## Separation of Duties

The decision handler in `backend/app/routers/risks.py` checks the following before it writes anything:

1. **Role.** Only `manager` and `admin` users can decide. Any signed-in user can submit an assessment, and each reviewer can assess a package only once.
2. **Two qualifying assessments.** At least two assessments must come from reviewers other than the deciding user. A manager's own assessment never counts toward the two, so one person cannot both review and decide.
3. **Current package and version.** The decision must reference the latest complete package for the risk and the current risk version. A stale package or a concurrent edit is rejected with HTTP 409.

When the qualifying count is too low the handler returns HTTP 422 with a structured body naming the deciding user and the current count, which the frontend shows to the manager.

The smallest valid workflow therefore has three distinct users: two reviewers who are not the decider, and the manager or admin who decides. The operator who created the risk can be one of the reviewers.

## Trade-offs

**Completeness rules are simple.** The check is field presence plus a minimum description length. It cannot tell a placeholder from a plan. In the evaluation, a mitigation of `TBD` passes as complete.

**Fallback perspectives carry no analysis.** They exist so the schema, the UI and the workflow run without an API key. The fallback picks its treatment from the score band alone (20 and above avoid, 12 to 19 mitigate, 6 to 11 transfer, below 6 accept), so it disagrees with reviewers on many mid-band risks that need controls rather than insurance. A reviewer who sees a fallback `source` should treat the perspectives as placeholders.

**The injection check is a short phrase list.** It looks for five fixed phrases in the title and description. It misses reworded attempts such as "ignore all previous instructions", it never sees `proposed_mitigation` or `business_unit` even though both are sent to the model, and it flags genuine risks that use the word "bypass". Flags are recorded and passed to the model but do not block anything.

**Past decision retrieval is basic.** The embedding is a 64-dimension signed hash of word tokens. Shared words raise similarity and synonyms do not, and unrelated texts can collide in the same buckets. In the evaluation, the expected precedent is in the top 3 for 6 of 10 cases, and one past risk about a flooded server room appears in 6 of the 10 top-3 lists, including cases about login attempts, intern access and currency exposure. The cause has not been isolated yet. Retrieval also scans every decided risk in Python on each request, which will not scale to a large register. A production version would use a real embedding model and a vector index for past decisions as well.

**Separation of duties lives in application code.** The checks run in the API handler, not in the database. A direct SQL write would bypass them. A production deployment should add a database constraint or trigger, or restrict write access to the decision table.

## Evaluation

`backend/evaluations/eval_decision_packages.py` runs every case in `backend/evaluations/risk_golden_set.json` through the real `generate_decision_package`. Each run creates a temporary in-memory SQLite database from the app's models and seeds it with the five risk management knowledge documents from `backend/app/seed.py` and the 12 decided past risks in `backend/evaluations/risk_past_decisions.json`.

The golden set has 43 fictional cases: 34 complete (18 clear, 16 borderline) and 9 incomplete, 7 injection attempts (5 in descriptions, 1 in `proposed_mitigation`, 1 in `business_unit`), and 10 cases that name the past decision a reviewer would cite. The labelling rules are at the top of the file.

What it measures, using only what the pipeline itself returns:

- completeness precision and recall, and whether the gap fields match the label
- package schema validity against `DecisionPackageOut`, the `Perspective` model and the allowed areas and treatments
- treatment agreement between `recommended_treatment` and the labelled treatment
- whether the exact expected past decision is among the 3 returned
- injection attempts flagged in the package's own `safety_flags`, and false flags on clean cases
- that no case leaves a `RiskDecision` row or a `decided` status behind
- the share of complete packages whose perspectives came from an LLM provider

Without arguments no API key is used and results go to `backend/evaluations/risk_results.json`. With `--provider openai` or `--provider anthropic` the script sets the provider, requires its API key, and writes `risk_results_<provider>.json`, so fallback and LLM numbers are never mixed. A provider run fails unless every complete package used the provider's output. Completeness, injection flags and past decision retrieval all run before the model call, so they are identical in both modes.

CI runs the fallback evaluation in the `backend-quality` job and fails the build when any metric drops below its floor. The current numbers are in the README.
