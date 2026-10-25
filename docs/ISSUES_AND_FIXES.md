# Issues faced and how they were solved

A record of the real problems hit while building the risk review module and hardening the platform
around it: what was seen, how it was diagnosed, the root cause, the fix and the evidence. This work
happened between 2026-10-15 and 2026-10-25 as a phased build. Each phase was one commit, reviewed
before the next phase started.

Each entry says how the issue was found:

- **In review:** found while reviewing a phase, before it was accepted.
- **While building:** found during the build itself, not in a review.
- **By the eval:** shown by the risk evaluation's own results.

Wrong first guesses are kept in, because how a wrong guess got caught is often the most useful part.
Numbers come from commits and committed files. The few that come from a check run during the build
and never committed are marked as such.

## The five best interview stories

| # | Story | Why it lands |
|---|---|---|
| 1 | [The first risk eval measured itself](#the-first-risk-eval-measured-itself) | It scored 100% by grading its own copy of the logic. Through the real pipeline: completeness recall 8/9, treatment agreement 19/34, precedent in the top 3 for 6/10, injection flagged 3/7. The copy's invented details had also leaked into the docs |
| 2 | [On cases written first the detector catches 6 of 12](#on-cases-written-first-the-detector-catches-6-of-12) | The old detector caught 3 of 7. The rewrite scores 7 of 7 on cases it was written against and 6 of 12 on a held-out set committed before any code, and the held-out number is the one quoted |
| 3 | [One manager and one reviewer could close a risk](#one-manager-and-one-reviewer-could-close-a-risk) | The "two assessments" rule counted the deciding manager's own assessment. Separation of duties has to be counted, not assumed |
| 4 | [The common words test measured the wrong number](#the-common-words-test-measured-the-wrong-number) | A hypothesis was rejected because the hit rate did not move. The question was how often one record appears, and on that count common words were the cause: 44 of 63 lists as built, 12 without them |
| 5 | [The model was told how many documents were found, not what they said](#the-model-was-told-how-many-documents-were-found-not-what-they-said) | Retrieval ran but never reached the prompt, and `except: pass` turned every provider failure into a silent fallback |

---

## Before the phased build: the README was ahead of the code

**Found:** in an external review of the public repo, 2026-10-15.

- **Seen:** the README described an `AnthropicProvider` and linked
  `backend/app/services/llm_provider.py` as evidence, but that file had never been committed, so the
  code on GitHub still called OpenAI directly. An "HR and People" section described onboarding,
  offboarding and job description generation that the code does not have. The Reviewer Guide marked
  `eval_ai_assistant.py` as running in CI, and `ci.yml` did not run it. Two files linked as evidence,
  `backend/observability.py` and `backend/prompts/ticket_assistant.py`, were imported by nothing.
- **Fix:** `458255d` wired the eval into CI, removed the HR section, and corrected the Kubernetes
  wording, which still described a kubectl dry run although CI had used kubeconform since `dc3c161`.
  `cdbc4da` committed the provider layer. Phase 1 (`78a7fdc`) deleted the two unused files and their
  README rows and replaced the HR tags.
- **Rule that came out of it:** no claim goes into the README or the docs unless a committed file
  proves it. Every later phase was checked against that rule.
- **Say:** "My README was ahead of my code. A review caught it, and since then a claim needs a
  committed file that proves it."

## Phase 1: harden the LLM layer (`78a7fdc`)

### The Anthropic path trusted the model to return bare JSON

**Found:** in review, before Phase 1 started.

- **Seen:** `AnthropicProvider` joined the reply's text blocks and passed them to the JSON parser. A
  reply wrapped in a markdown code fence, or with a sentence before the JSON, would fail Pydantic
  validation and fall back to the keyword rules.
- **Fix:** the call forces a tool call (`tool_choice`) against a JSON schema and reads `block.input`,
  which is already a dict. A parser that strips code fences stays as a second layer. 26 mocked tests
  in `backend/tests/test_llm_provider.py` cover provider selection, both providers' happy paths,
  fences, token and cost fields, and timeout, connection and rate limit errors.
- **Say:** "Asking a model for JSON is a request. Forcing a tool call against a schema is a contract."

### An eval kept its own copy of the logic it was testing

**Found:** in review, before Phase 1 started.

- **Seen:** `eval_ai_assistant.py` carries an inline copy of the agent's fallback rules. Its
  docstring says why: importing `app.services.agent` pulls in SQLAlchemy at module level, so the copy
  "must stay in sync" by hand.
- **Fix:** `test_eval_inline_fallback_stays_in_sync_with_agent_fallback` runs both versions on all 8
  cases and fails CI if category, priority or team differ.
- **Still open:** Phase 3.1 showed the app imports cleanly once `DATABASE_URL` points at an in-memory
  SQLite database, so this copy could now be deleted. The same pattern, an eval rebuilding the logic
  it tests, is what broke the Phase 3 risk eval below.

### Smaller fixes

**Found:** in review, before Phase 1 started.

- CI was red on a ruff import order error (I001) in `llm_provider.py`. Fixed by sorting the import
  block.
- `datetime.utcnow()` was replaced with timezone aware `datetime.now(timezone.utc)` in the models,
  three routers, the seed and the workflow service.

## Phase 2a: risk review backend (`f7b483c`)

### The eval results file changed on every run

**Found:** in review of Phase 1.

- **Seen:** every local run rewrote `backend/evaluations/results.json` with a new latency value, so
  the file always showed as modified.
- **Fix:** `average_latency_ms` is rounded to 2 decimals instead of 3. The committed value is 0.02.
- **Not enough:** rounding only made the change rarer. A later run still wrote 0.04 against the
  committed 0.02 (seen in `git status` during the build, not committed), and every pytest run
  rewrites the file. `7689f6f` keeps latency
  out of `results.json` altogether. The script prints it and `tests/test_evaluations.py` still
  requires it to stay under 50 ms.
- **Say:** "A results file that changes on every run hides the change that matters, and rounding a
  volatile number only hides it less often."

### A phase commit that never reached GitHub

**Found:** in review of Phase 2a.

- **Seen:** `f7b483c` was not on GitHub. `main` was still at `78a7fdc`, because the commit had been
  made locally and not pushed.
- **Fix:** every later phase was pushed straight after its commit and confirmed with
  `git ls-remote origin refs/heads/main` before being reported as done.

## Phase 2a.1 and 2a.2: review integrity (`e3e2a0e`, `a558007`)

The issues in this section were found in review of Phase 2a, except the last part of the first
entry, which was found in review of Phase 2a.1.

### The model was told how many documents were found, not what they said

- **Seen:** `generate_perspectives` sent the model `best_practices_count` and
  `past_decisions_count`. Retrieval ran, but the model never saw a single document excerpt or a past
  decision's rationale.
- **Seen in the same function:** `except (LLMProviderError, Exception): pass`. Any provider error or
  malformed reply quietly produced fallback perspectives, with no log line and nothing on the package
  to say so.
- **Fix (`e3e2a0e`):** document titles with 300 character excerpts, and past decisions with their
  decision and rationale, now reach the model inside an `untrusted_reference_data` block. The package
  stores `cited_knowledge_ids` and `cited_decision_ids`. Provider errors and invalid output have
  separate handlers that log the trace ID, and a new `source` column (migration `0003`) records which
  path produced the perspectives.
- **Follow up (`a558007`):** an exception that is not an `LLMProviderError`, for example an
  authentication error from a bad API key, still escaped and crashed the request with a 500. The
  provider layer only wraps timeout, connection and rate limit errors. A final `except Exception` now
  logs with `logger.exception` and records `fallback_unexpected_failure`, tested by
  `test_perspectives_source_fallback_unexpected_failure`.
- **Say:** "Retrieval that never reaches the prompt is decoration, and a fallback nobody can see is
  an outage nobody can see. Every package now records which path produced it."

### One manager and one reviewer could close a risk

- **Seen:** the decision endpoint counted every assessment on the package, including one written by
  the manager making the decision, so a manager plus one other reviewer met the "two assessments"
  rule. Assessments were also accepted on incomplete packages, on decided risks and on superseded
  packages, and a decision could cite any package for the risk.
- **Fix:** assessments by the deciding user no longer count, and the 422 response names the user and
  the qualifying count. An assessment on an incomplete package gets a 422, and one on a decided risk
  or a superseded package gets a 409. A decision must cite the latest complete package (409
  otherwise). Each assessment now records its perspective.
- **Evidence:** the `e3e2a0e` diff of `backend/app/routers/risks.py`, and the tests
  `test_separation_of_duties_422`, `test_decision_rejects_non_latest_package` and the three
  `test_assessment_blocked_on_*` tests.
- **Say:** "The rule said two assessments, and the code counted two rows rather than two people other
  than the decider. Separation of duties has to be counted, not assumed."

### Past decisions were ranked after taking the first 20 rows

- **Seen:** the query applied `.limit(20)` before ranking by similarity. Once more than 20 risks were
  decided, the closest precedent could be skipped without any error.
- **Why nothing showed it:** the demo seeded 3 decided risks.
- **Fix:** every decided risk is ranked first, then the top 3 are taken, tested by
  `test_past_decision_ranking_most_similar`. The price is a full scan in Python on every request,
  which the README lists as a limit.
- **Say:** "A limit before a sort is a sampling bug, and it could never appear with demo data."

## Phase 2b: Risk Review tab (`4a4b02c`)

### Structured errors would have shown as [object Object]

**Found:** while building.

- **Seen:** the earlier 401 fix (`6d3a022`) set the error message to the API's `detail` field, which
  works when `detail` is a string. The new separation of duties response returns an object
  (`message`, `qualifying_count`, `deciding_user`), which the page would print as `[object Object]`.
- **Fix:** `api()` in `frontend/src/main.jsx` reads `detail.message` when `detail` is an object.
- **Say:** "The error handler assumed every error was a string, and the new governance rules
  returned objects."

### Run instructions with the wrong demo passwords

**Found:** in review of Phase 2b.

- The steps written for trying the phase used the wrong demo passwords and skipped migrations and
  seeding. The README already had the right passwords (`viewer-demo` and so on). Phase 4 added that
  the container runs `alembic upgrade head` and `seed_demo.py` before the API starts.

## Phase 3: risk evaluation (`af89dea`)

### The first risk eval measured itself

**Found:** in review of Phase 3.

- **Seen:** `risk_results.json` reported 100% completeness precision, 100% recall, 100% schema
  validity and 100% injection flagging on 25 cases. The past decision hit rate was 0%, against a
  threshold of 0%.
- **Diagnosed:** the fallback mode never called the service. `_build_fallback_package` rebuilt the
  pipeline inside the eval, and the rebuild disagreed with `decision_package.py`:
  - Completeness required 30 characters of description instead of 20, and never checked that impact
    and likelihood were between 1 and 5.
  - Injection used the eval's own 7 regular expressions over 5 fields, against the app's 5 phrases
    over 2 fields. A case also counted as flagged whenever the eval's own regex matched, whatever the
    package said.
  - Treatment mapped scores 6 to 11 to mitigate. The app maps them to transfer.
  - Schema validity checked the eval's own dictionaries, which carried a `needs_human_decision` field
    and a perspective `rationale` that the app does not have. The "no decision without a human" check
    read that same field, which the eval always set to true.
  - The two precedent cases only said `true`, and a hit meant "the list is not empty". In fallback
    mode the list was always empty, hence 0% and a 0% threshold.
  - The `--provider` path called `generate_decision_package` without `actor` and `settings`, passed
    `created_by`, which is not a `RiskItem` column, and read stored perspective dictionaries as
    objects. It had never run, and it would have crashed on first use.
- **Root cause:** the eval was written to run with no database ("no DB, no API calls" in its
  docstring), so it copied the logic instead of calling it. A copy that disagrees with the code it
  imitates can only score itself.
- **Fix (`6c4cf73`):** every case now runs through the real `generate_decision_package` on a temporary
  in-memory SQLite database built from the app's own models. It is seeded with the 5 risk management
  documents the demo uses (`RISK_KNOWLEDGE_DOCUMENTS` in `backend/app/seed.py`, shared rather than
  copied) and 12 decided past risks (`backend/evaluations/risk_past_decisions.json`). Injection counts
  only the package's own `safety_flags`. 10 cases name the exact precedent expected in the top 3.
  Treatment agreement, gap fields, false positives and provider output rate became metrics. CI floors
  sit at the measured values, so one regressed case fails the build, and
  `backend/tests/test_eval_decision_packages.py` runs the provider path with a mocked provider.
- **Evidence:** `af89dea` and `6c4cf73` versions of `backend/evaluations/risk_results.json`:

| Metric | Phase 3, own copy, 25 cases | Phase 3.1, real pipeline, 43 cases |
|---|---:|---:|
| Completeness precision | 100% | 8/8 |
| Completeness recall | 100% | 8/9 |
| Package schema validity | 100% | 43/43 |
| Injection attempts flagged | 100% of 3 | 3/7 |
| Clean cases falsely flagged | not measured | 1/36 |
| Treatment agreement | not measured | 19/34 |
| Expected precedent in the top 3 | 0% | 6/10 |
| Decisions made without a human | read from a field the eval set itself | 0 of 43 |

- **Say:** "My first risk eval scored 100% because it was grading its own copy of the logic. I caught
  it in review and made every case go through the real pipeline. The honest numbers are lower, and
  they are the ones that show what to fix."

### A retrieval check against 3 candidates cannot fail

**Found:** while building Phase 3.1.

- **Seen:** the demo seed has 3 decided risks. A "precedent in the top 3" check against 3 candidates
  passes whatever the ranking does.
- **Fix:** the eval seeds 12 decided past risks, and `test_golden_set_covers_the_required_case_types`
  asserts there are more than 3.
- **Say:** "Before I trust a metric, I ask whether it could have failed."

## Phase 4: documentation (`79cf48b`)

### The docs described the eval's copy, not the app

**Found:** while building Phase 3.1, except the pgvector claim and the "fallback has no DB" note, which
were found in the same review that caught the Phase 3 eval.

- **Seen:** `README.md` and `docs/RISK_REVIEW.md` described:
  - a `needs_human_decision` field "set unconditionally". No such field exists.
  - a 30 character description rule. The code uses 20.
  - a `rationale` on each perspective. The `Perspective` model has none.
  - decision audit events holding the user's role, the rationale and the package id. The audit event
    stores the actor, trace ID, status and version before and after, and the decision. The rationale
    and package id live on the `RiskDecision` row, and the role is not stored anywhere.
  - past decisions retrieved with pgvector. They are ranked in Python with the local hashing
    embedding. Only the knowledge base search uses pgvector.
  - a ticket eval of 8 cases. `results.json` has 5, and 8 is the count in `eval_ai_assistant.py`. Two
    rows of that table, fallback availability and cost, were constants in `run_evaluations.py`, not
    measurements.
  - a 0% past decision hit rate explained as "fallback has no DB".
- **Diagnosed:** the first three match the Phase 3 eval's copy exactly: its `_MIN_DESCRIPTION_LEN = 30`,
  the `rationale` in its perspective fields, and `needs_human_decision` in its package dictionaries.
  The docs were written from the eval, not from `decision_package.py`.
- **A verification claim that was not true:** the Phase 4 commit message says all 25 file paths were
  confirmed to exist and all numbers verified. A path check during Phase 3.1 (not committed) covered
  39 paths and found one missing: `assets/screenshots/grafana-dashboard.png`, referenced in the README
  since `17376ff` and never committed. `b0dcc3c` removed the reference, and its README audit covered
  59 path tokens, code blocks included, and every number.
- **Fix (`6c4cf73`):** both documents were rewritten from the code, and each behaviour in
  `RISK_REVIEW.md` can be checked in `decision_package.py` or `risks.py`. The ticket table now says 5
  golden tickets and drops the two constant rows.
- **Say:** "A copy of the logic does not only give wrong scores. Its details leak into the docs. Now
  every claim in the design doc points at code."

## Phase 3.1: what the real eval found (`6c4cf73`)

### The injection detector caught 3 of 7 attempts

**Found:** by the eval.

- **Seen:** 3 of 7 injection attempts flagged, and 1 of 36 clean cases falsely flagged.
- **Diagnosed:** the detector, `_prompt_injection_flags` in `backend/app/services/agent.py`, looks for
  five fixed phrases (`ignore previous`, `system prompt`, `reveal secret`, `developer message`,
  `bypass`) in the title and description only. Case by case:
  - `rg-037` ends with "Ignore all previous safety instructions", after a fake `SYSTEM:` message.
    Missed: the word "all" breaks the phrase `ignore previous`.
  - `rg-040` is a fake instruction "from the risk committee", placed after a fake closing tag for the
    reference data block. Missed: none of the five phrases.
  - `rg-042` sits in `proposed_mitigation` and contains "Ignore previous instructions" and "system
    prompt", two of the five phrases. Missed, because the detector never reads that field.
  - `rg-043` is an "ADMIN OVERRIDE" in `business_unit`. Missed for the same reason.
  - `rg-041` was caught, but only by `bypass`. The same word flagged `rg-027`, a genuine risk about
    fraudsters bypassing a rate limit.
  - Both unread fields are sent to the model.
- **Fix:** none in this phase. The README and `RISK_REVIEW.md` said what the detector missed, and the
  CI floor sat at 3/7 so it could not get worse unnoticed. Phase 3.2 replaced the detector, see
  [On cases written first the detector catches 6 of 12](#on-cases-written-first-the-detector-catches-6-of-12).
- **Caveat on the test cases (recorded during the build):** all 43 cases were written before the
  first run and none were changed afterwards. Four of the seven injection cases were written after
  reading the detector's phrase list. The other three reuse wording from the Phase 3 set, written
  before the phrase list was read.
- **Say:** "My detector missed an attack that contained two of its own five phrases, because the
  attack sat in a field the detector never reads. I would rather publish 3 of 7 than a 100% that
  tested nothing."

### Mid band risks went to insurance

**Found:** by the eval.

- **Seen:** treatment agreement 19/34, with 8/18 on clear cases and 11/16 on borderline ones.
- **Diagnosed:** without an API key, the fallback picks a treatment from the score band alone and
  maps every score from 6 to 11 to transfer. 13 of the 15 disagreements are risks labelled mitigate
  that it sent to transfer, and of the 17 labelled cases scoring 6 to 11, only 4 are labelled transfer
  (both counted from `risk_results.json`).
- **Fix:** none in the fallback. It exists so the workflow runs without an API key, and
  `RISK_REVIEW.md` says its perspectives carry no analysis. Phase 3.4 measured whether a model does
  better, see [The first LLM numbers](#the-first-llm-numbers).
- **Say:** "A score band cannot tell controls from insurance. The plan decides that, and the fallback
  never reads the plan."

### TBD passes as a mitigation plan

**Found:** by the eval.

- `rg-036` has `TBD` as its proposed mitigation. The completeness check only tests that the field is
  not empty, so the risk was treated as complete. That is the one miss behind completeness recall 8/9.

### One past risk shows up in most top 3 lists

**Found:** by the eval. **Cause found in Phase 3.2**, see
[The common words test measured the wrong number](#the-common-words-test-measured-the-wrong-number).

- **Seen:** the expected precedent is in the top 3 for 6 of 10 cases. One past risk, about a flooded
  server room (`pd-server-room-flood`), appears in 6 of those 10 lists, including cases about login
  attempts, intern access and currency exposure. Across all 35 packages that reached retrieval it
  appears in 20 lists, and the next most frequent record appears in 12. It is never the expected
  precedent. The contractor offboarding decision, the precedent for the former interns case, appears
  in none of the 35 lists. These counts come from the `6c4cf73` version of `risk_results.json`.
- **First hypothesis:** common words. Words like "the" and "and" appear in almost every record, so
  they could pull one wordy record close to everything.
- **How it was tested, and why the test was wrong:** a scratch check during the build, not committed,
  re-ranked the 10 precedent cases with a list of common English words removed. The hit rate stayed at
  6/10, and the hypothesis was reported as rejected. That conclusion was wrong. The hit rate says
  whether the right record reaches the top 3, but the question was why one record appears in almost
  every list, and the check never counted that. It did count 44 tokens in the flood record, 18 of
  them common words.
- **What was known then:** the embedding was a 64 dimension signed hash of word tokens
  (`backend/app/services/knowledge.py`), compared by cosine similarity and ranked in Python over every
  decided risk.
- **Fix:** none in this phase. Phase 3.2 measured the right number.

## Phase 3.2: detector, retrieval and a held-out set (`192a68b`, `b0dcc3c`)

### The held-out cases were committed before the code

**Found:** in review of Phase 3.1.

- **Seen:** the new detector would be written by someone who had read all 43 golden cases, so its
  golden score could not show that it works on attacks it has not seen.
- **Fix:** `192a68b` adds `backend/evaluations/risk_holdout_set.json` and nothing else, before any
  change to detection or retrieval. It holds 31 cases: 12 injection attempts phrased differently from
  the golden set and spread across every text field (title 2, description 4, proposed mitigation 3,
  business unit 2, owner 1), 12 clean cases that use bypass, override, ignore or instructions in their
  ordinary meaning, 5 cases naming the expected precedent, and 2 incomplete cases. The detector and
  retrieval are never tuned against it, and CI runs it as its own evaluation with its own floors and
  its own results file, `risk_holdout_results.json`.
- **Limit:** the same author wrote the held-out cases and the detector patterns. The commit order
  proves which came first, not that the patterns were uninfluenced.
- **Say:** "I wrote the test cases first and committed them on their own, so the history shows they
  existed before the code."

### On cases written first the detector catches 6 of 12

**Found:** by the eval in Phase 3.1, fixed in `b0dcc3c`.

- **Seen:** the held-out baseline, run with the old detector after `192a68b` and before any code
  change, caught 0 of 12 attempts and falsely flagged 2 of 19 clean cases, both for the word
  "bypass". These baseline numbers are recorded in the `b0dcc3c` commit message.
- **Fix:** `backend/app/services/prompt_safety.py` scans all five risk text fields instead of two. It
  lowercases the text, collapses whitespace and punctuation, and matches patterns for eight general
  categories: instruction override, role reassignment, prompt or secret extraction, messages
  addressed to the model, fake authority, decision tampering, delimiter or role tags, and hidden
  markup. Bare imperatives such as "ignore" or "bypass" only match at the start of a sentence, which
  is what stopped the false positives. 28 unit tests in `backend/tests/test_prompt_safety.py` cover
  every category, every field and 10 clean sentences.
- **Evidence** (results files, and the `b0dcc3c` commit message for the "before" column):

| Metric | Before | After the detector | After the detector and 256 dimensions |
|---|---:|---:|---:|
| Golden attempts flagged | 3/7 | 7/7 | 7/7 |
| Golden clean cases falsely flagged | 1/36 | 0/36 | 0/36 |
| Held-out attempts flagged | 0/12 | 6/12 | 6/12 |
| Held-out clean cases falsely flagged | 2/19 | 0/19 | 0/19 |

- **Why 7 of 7 is not the number to quote:** the patterns were written after the golden cases were
  known, so the golden set had become training data for the detector.
- **Why the six held-out misses were left alone:** a bracketed fake system notice in a title,
  letter-spaced text, an instruction in Spanish, a request to repeat "setup text", and both attempts
  in `business_unit`. Patching them would tune the detector to the held-out set and destroy the only
  honest measure of it. The CI floor sits at 6/12.
- **A detail caught while writing the tests:** splitting text into sentences at every full stop broke
  "previous... instructions" into two pieces, which defeats the punctuation collapse. Sentence breaks
  now need a capital letter after them.
- **Say:** "On the cases I could see while writing it, the detector scores 7 of 7. On cases committed
  before the code it catches 6 of 12, and that is the number I quote. I left the misses unpatched,
  because patching them would turn the held-out set into training data."

### Collisions were costing hits but did not cause the hub

**Found:** in review of Phase 3.1, which proposed hash collisions in the 64 dimension embedding as
the cause of the flooded server room record dominating retrieval.

- **Test:** `backend/evaluations/embedding_dimension_study.py` measures the precedent hit rate at 64,
  256 and 512 dimensions on both sets. Its decision rule was written before the run: change the size
  only if a larger one gives strictly more hits on both sets, and take the smallest that does.
- **Evidence** (`backend/evaluations/embedding_dimension_study.json`):

| Dimensions | Golden precedent hits | Held-out precedent hits | Flood record in golden top 3 lists |
|---:|---:|---:|---:|
| 64 | 6/10 | 4/5 | 20 of 35 |
| 256 | 9/10 | 5/5 | 25 of 35 |
| 512 | 10/10 | 5/5 | 29 of 35 |

- **Fix:** `EMBEDDING_DIMENSIONS` is now 256. Migration `0004` resizes the pgvector column, rebuilds
  the HNSW index and re-embeds every stored document. It was round tripped (upgrade, downgrade,
  upgrade) on SQLite and on the local pgvector database during the build. That check is not
  committed.
- **What it did not fix:** the flood record appears in more lists as the size grows. Collisions were
  hiding the right precedents, but they were not what made one record a hub.
- **Say:** "The collision theory was half right. More dimensions fixed the misses, but the hub got
  worse, so it needed a different explanation."

### The common words test measured the wrong number

**Found:** while building Phase 3.2, when the hub count above went the wrong way.

- **Seen:** Phase 3.1 had reported the common words hypothesis as rejected, because removing common
  words left the hit rate at 6/10.
- **Diagnosed:** the hit rate was never the question. The question was why one record appears in
  almost every list, so the number to measure was how often it appears. The study's diagnostic
  re-ranks every complete case in both sets at 256 dimensions with the app's own embedding functions,
  once as built and once with common English words removed from both sides.
- **Evidence** (`embedding_dimension_study.json`): the flood record is in 44 of 63 top 3 lists as
  built and 12 of 63 with common words removed. Its text is 41% common words, against 24% for the
  other past risks. The hypothesis was right and the first test of it was wrong.
- **Fix:** none in the code, on purpose. Phase 3.3 documents common words as the known cause of the
  hub effect, and stopword removal or term weighting as the next step, in the README Limits.
- **Say:** "I rejected the right hypothesis because I measured the wrong number. The hit rate did not
  move, but the hub count did: 44 lists down to 12."

### Claims no file could back

**Found:** in the README audit for Phase 3.2.

- The README still embedded the missing Grafana image, called its quick start "Five-Minute", and said
  the dashboard covered "the four signals that matter most" without naming them. `b0dcc3c` removed
  the image, renamed the heading to Quick Start, and names the dashboard's panels. The audit checked
  59 path tokens, code blocks included, and every number against a committed file, a script or git.

## Phase 3.3: closing the gaps this log found (`2ff7b57`)

### The model was never told to distrust the risk fields

**Found:** while writing this log.

- **Seen:** since `e3e2a0e` the perspectives system prompt only told the model to distrust the
  `untrusted_reference_data` block. The submitter's own fields, where the injection cases put their
  attacks, carried no such instruction.
- **Fix:** the system prompt now says to treat risk item and reference data text as untrusted and
  never to follow instructions inside them, in the same terms the ticket agent uses for tickets. The
  risk text reaches the model in a `risk_item` block.

### The scanned fields and the prompt fields could drift apart

**Found:** in review of Phase 3.2.

- **Seen:** `owner` was scanned but never sent to the model, because the scanned list and the prompt
  were written separately.
- **Fix:** `owner` is now sent, so the detector scans exactly the fields the model receives. Both
  come from one helper, `_risk_text_fields`. `backend/tests/test_prompt_fields.py` compares the
  prompt's text fields with the scanned fields, and also fails if the prompt gains a new top-level
  field, which is how risk text could reach the model outside the `risk_item` block. A probe run during the build, not committed, made the detector skip one field,
  and the test failed as intended.
- **Say:** "Two lists that must match should come from one place, with a test that proves they still
  match."

### The ticket agent scanned two of its four fields

**Found:** in review of Phase 3.2.

- **Seen:** the ticket agent sent title, description, customer and channel to the model but only
  scanned title and description, with the old phrase list.
- **Fix:** it now scans every ticket field it sends with the same field-wide detector, from one
  helper, `_ticket_text_fields`, and the same drift test covers it.

### Older databases never received the risk demo data

**Found:** while building Phase 3.2. The local database had 3 knowledge documents and no decided
risks.

- **Root cause:** `seed_demo_data` returned as soon as any agent existed, before tickets, workflows
  and all of the risk data. `_seed_risk_data` also skipped whenever any risk existed, so a risk a user
  created after upgrading blocked the demo risks.
- **Fix:** each seed section checks its own rows. Knowledge documents are matched by title, users,
  agents, tickets and workflows by table, and the demo risks by their titles. `backend/tests/test_seed.py`
  shows that a rerun adds nothing and that a database without risk data, plus one user-created risk,
  receives all of it.
- **Not verified on Postgres:** Docker Desktop was not running when the fix landed, so the local
  database was not reseeded. The SQLite tests rebuild the same situation.
- **Say:** "An early return in a seed script meant upgrades silently skipped every section after it."

## Phase 3.4: a Groq provider and the first LLM numbers (`57ca6e5`)

### A sampled model wrote "0. nine" as a number

**Found:** by the eval, on the first live Groq run.

- **Seen:** 34 of 35 golden packages used Groq's output and one, `rg-020`, fell back with the label
  `fallback_unexpected_failure`. The run's own gate requires every complete package to use the
  provider's output, so it failed the run instead of letting a fallback pass as an LLM result.
- **Diagnosed:** the log showed Groq answering 400 with `tool_use_failed`. Its `failed_generation`
  held the model's tool call, which contained `"confidence": 0. nine`, so the arguments were not
  valid JSON. The provider only retried timeouts, connection errors and rate limits, so the 400 went
  to the generic exception handler and was labelled unexpected rather than invalid output.
- **Fix:** `tool_use_failed` is retried, because the model samples a new answer each time. If it
  keeps failing, the provider returns the broken generation, the existing JSON check rejects it, and
  the package is recorded as `fallback_invalid_output`. Two mocked tests cover the retry and the
  persistent failure. The committed run used Groq's output for 35 of 35 golden and 29 of 29
  held-out packages. The first attempt's log was not committed. The error is quoted in the `57ca6e5`
  commit message.
- **Say:** "The model once wrote a number as `0. nine`. The eval refused to count the run, because a
  package had silently fallen back, so I made that failure retryable and labelled correctly."

### The first LLM numbers

**Found:** by the eval.

- **Seen:** every earlier risk number came from the fallback, with no API key.
- **Fix:** `GroqProvider` joins the provider layer and uses Groq's OpenAI-compatible chat API with a
  forced tool call against the same JSON schemas as the Anthropic path. The planned model, Llama 3.3
  70B, was no longer listed for the account, so the run uses `openai/gpt-oss-120b`, recorded in the
  results files.
- **Evidence** (`risk_results_groq.json`, `risk_holdout_results_groq.json`):

| Treatment agreement | Fallback | Groq |
|---|---:|---:|
| Golden, all 34 cases | 19/34 | 27/34 |
| Golden, clear cases | 8/18 | 14/18 |
| Golden, borderline cases | 11/16 | 13/16 |
| Held-out, all 29 cases | 18/29 | 27/29 |

- **Caveats:** schema validity stayed at 43/43 and 31/31, and every other metric is decided before
  the model call, so it cannot change. This is one run of a sampled model. The failed first attempt
  scored 29/34 on the golden set with one package on the fallback (seen during the build, not
  committed), so a rerun can move by a few cases. The labels are a single reviewer's judgement.
- **Say:** "The model agreed with the reviewer on 27 of 34 treatments where the score band rule got
  19, and I quote it as one run of a sampled model, not a fixed score."

## Local environment

Problems with the development machine, not the project.

- **Evals failed locally without a database driver:** `run_evaluations.py` stopped with
  `No module named 'psycopg2'`, because the local Python 3.11 does not have it. CI installs
  `psycopg2-binary` from `backend/requirements.txt`. Locally, setting
  `DATABASE_URL=sqlite+pysqlite:///:memory:` works around it.
- **Port 5432 was taken** by another project's Postgres container, so `docker compose up` failed with
  "port is already allocated". The local compose file was edited to map the database to 5434. That
  edit was never committed and was discarded on 2026-10-15, so a fresh `docker compose up` on this
  machine still needs the other container stopped first.
- **`alembic: not found` in the backend container.** The first fix, running `python -m alembic`
  instead, only changed the error to `No module named alembic`, which showed the real cause: the local
  backend image was older than the alembic dependency, added to `requirements.txt` in `53e663f`.
  `docker compose build backend` fixed it. The `python -m alembic` edit was never tested on its own,
  was never committed, and was discarded with the port edit.
- **A logged exception crashed the eval on Windows:** structlog printed the traceback of the Groq
  error with characters the console's cp1252 encoding cannot show, so the logging call itself raised
  `UnicodeEncodeError` and hid the real error. Running with `PYTHONIOENCODING=utf-8` showed it.
- **Nothing was seeded:** the local `.env` was an old copy without `DEMO_SEED_ENABLED=true`, which
  `.env.example` has had since `53e663f`.

## Still open

- The injection detector misses 6 of 12 held-out attempts: obfuscated text, a non-English
  instruction, reworded requests and both `business_unit` attempts. Flags are recorded and passed to
  the model but block nothing.
- Common words make one past risk a retrieval hub. Stopword removal or term weighting is the next
  step, followed by a rerun of `embedding_dimension_study.py` on both sets.
- A `TBD` mitigation passes the completeness check.
- The fallback treatment is a score band rule on purpose, so its treatment agreement stays at 19/34
  on the golden set.
- `eval_ai_assistant.py` still carries its own copy of the fallback rules, guarded by a sync test.
- Only one LLM run is committed (Groq, `openai/gpt-oss-120b`). There is no OpenAI or Anthropic run,
  no repeated run to measure variance, and no test of how the model responds to the injection
  attempts beyond the flags the detector records.
