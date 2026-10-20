# Risk Review

This document explains how decision packages are built, why the AI recommends but never decides, how separation of duties is enforced, and the trade-offs involved. Every behaviour described here can be checked in `backend/app/services/decision_package.py` and `backend/app/routers/risks.py`.

## Decision Package Design

A decision package is what an operator gets back after asking the system to analyse a risk item. It puts everything a reviewer needs in one place before anyone votes.

The package is built by a LangGraph `StateGraph` in `backend/app/services/decision_package.py`:

1. **Completeness check.** The pipeline requires an owner, impact and likelihood between 1 and 5, a proposed mitigation, and a description of at least 20 characters. If anything is missing the graph ends here, the package is saved with `needs_info=true` and a list of gaps, and no LLM call is made. Assessments cannot be added to an incomplete package. The same step runs `scan_fields` from `backend/app/services/prompt_safety.py` over the title, description, proposed mitigation, business unit and owner, and records each match in `safety_flags` as `prompt_injection:<category>:<field>`. The detector lowercases the text, collapses whitespace and punctuation, and matches patterns for eight categories: instruction override, role reassignment, prompt or secret extraction, messages addressed to the model, fake authority, decision tampering, delimiter or role tags, and hidden markup. Bare imperatives such as "ignore" or "bypass" only match at the start of a sentence, and the other patterns need wording aimed at the model, its instructions or the risk outcome, such as "you are now", "your instructions", "system prompt", "previous instructions" or "mark this risk as approved". That keeps ordinary risk text that says bypass, override or ignore from being flagged. These five are exactly the text fields sent to the model, and `backend/tests/test_prompt_fields.py` fails if the scanned fields and the prompt fields drift apart.

2. **Best practice retrieval.** The 3 closest knowledge base documents are attached as `best_practices`. On PostgreSQL this search uses pgvector. On SQLite it ranks the stored local embeddings in Python.

3. **Past decision retrieval.** Every decided risk is embedded with the deterministic 256-dimension local hashing function in `backend/app/services/knowledge.py`, ranked by cosine similarity against the new risk, and the top 3 are attached as `past_decisions` with their decision and rationale. This step runs in Python on every database and does not use pgvector.

4. **Perspective generation.** The provider-agnostic LLM layer returns security, compliance and business perspectives. Each has key concerns, reviewer questions, a suggested treatment and a confidence score. The risk fields are passed in a `risk_item` block and the reference documents and past decisions in an `untrusted_reference_data` block. The system prompt tells the model to treat both as untrusted data and never follow instructions embedded inside them, in the same terms the ticket agent uses for tickets. When no API key is set, or the provider fails or returns invalid output, deterministic fallback perspectives are used instead. The `source` field records which path produced the perspectives: `openai_structured_output`, `anthropic_messages`, `fallback_no_provider`, `fallback_invalid_output`, `fallback_provider_failure`, `fallback_unexpected_failure`, or `seed` for demo data.

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

**Fallback perspectives carry no analysis, by design.** The fallback is a safety net that keeps the schema, the UI and the workflow running when no LLM is available. It is not a substitute for the model, so its treatment logic is deliberately left as a score band rule (20 and above avoid, 12 to 19 mitigate, 6 to 11 transfer, below 6 accept). It disagrees with reviewers on many mid-band risks that need controls rather than insurance: 19 of 34 golden cases agree. A reviewer who sees a fallback `source` should treat the perspectives and the suggested treatment as placeholders.

**The injection check is pattern matching.** It flags 7 of 7 golden attempts, but the patterns were written after those cases were known. On the held-out set, written and committed first, it flags 6 of 12. It misses a bracketed fake system notice, letter-spaced text, a Spanish instruction, a request to repeat "setup text", and both attempts in `business_unit`. These were not patched, because that would tune the detector to the held-out set. It produces no false flags on either set (0 of 36 and 0 of 19 clean cases), including 12 held-out cases that use bypass, override, ignore or instructions normally. Flags are recorded and passed to the model but do not block anything.

**Past decision retrieval is basic.** The embedding is a signed hash of word tokens with no stopword removal or term weighting. `backend/evaluations/embedding_dimension_study.py` measured the expected precedent hit rate at 64, 256 and 512 dimensions: 6/10, 9/10 and 10/10 on the golden set, and 4/5, 5/5 and 5/5 on the held-out set. Hash collisions at 64 dimensions were costing hits, so the size moved to 256, the smallest that improved both sets, with migration `0004` resizing the pgvector column, rebuilding the HNSW index and re-embedding stored documents. Collisions were not the cause of the hub, though: the past risk about a flooded server room appears in more top-3 lists at 256 dimensions than at 64 (25 of 35 golden lists against 20). The study's diagnostic re-ranking shows that common words cause it. That text is 41% stopwords against 24% for the other past risks, and with stopwords removed it falls from 44 to 12 of 63 top-3 lists. Stopword handling is deliberately not added yet. It is the next step: remove stopwords or weight terms before hashing, then rerun the study on both sets to confirm the hub is gone and the hit rate holds. Retrieval also scans every decided risk in Python on each request, which will not scale to a large register. A production version would use a real embedding model with a vector index for past decisions as well.

**Separation of duties lives in application code.** The checks run in the API handler, not in the database. A direct SQL write would bypass them. A production deployment should add a database constraint or trigger, or restrict write access to the decision table.

## Evaluation

`backend/evaluations/eval_decision_packages.py` runs every case in a case set through the real `generate_decision_package`. Each run creates a temporary in-memory SQLite database from the app's models and seeds it with the five risk management knowledge documents from `backend/app/seed.py` and the 12 decided past risks in `backend/evaluations/risk_past_decisions.json`. There are two case sets, run separately with separate results files:

- `backend/evaluations/risk_golden_set.json` (default, results in `risk_results.json`) has 43 fictional cases: 34 complete (18 clear, 16 borderline) and 9 incomplete, 7 injection attempts (5 in descriptions, 1 in `proposed_mitigation`, 1 in `business_unit`), and 10 cases that name the past decision a reviewer would cite. The labelling rules are at the top of the file.
- `backend/evaluations/risk_holdout_set.json` (`--set holdout`, results in `risk_holdout_results.json`) has 31 cases committed before any detection or retrieval change: 12 injection attempts phrased differently from the golden set across all five text fields, 12 clean cases that use bypass, override, ignore or instructions in their ordinary meaning, 5 cases that name a past decision, and 2 incomplete cases. Detection and retrieval must never be tuned against it.

What it measures, using only what the pipeline itself returns:

- completeness precision and recall, and whether the gap fields match the label
- package schema validity against `DecisionPackageOut`, the `Perspective` model and the allowed areas and treatments
- treatment agreement between `recommended_treatment` and the labelled treatment
- whether the exact expected past decision is among the 3 returned
- injection attempts flagged in the package's own `safety_flags`, and false flags on clean cases
- that no case leaves a `RiskDecision` row or a `decided` status behind
- the share of complete packages whose perspectives came from an LLM provider

Without `--provider` no API key is used and the fallback results files are written. With `--provider openai` or `--provider anthropic` the script sets the provider, requires its API key, and adds `_<provider>` to the results file name, so fallback and LLM numbers are never mixed. A provider run fails unless every complete package used the provider's output. Completeness, injection flags and past decision retrieval all run before the model call, so they are identical in both modes.

CI runs the fallback evaluation on both sets in the `backend-quality` job and fails the build when any metric drops below its floor. The current numbers are in the README.
