"""Measure past decision retrieval at several local embedding sizes on the golden and held-out risk sets."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections import Counter
from pathlib import Path

import structlog

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")

from app.core.config import Settings  # noqa: E402
from app.services import knowledge  # noqa: E402
from evaluations import eval_decision_packages as risk_eval  # noqa: E402

DIMENSIONS = (64, 256, 512)
OUT_PATH = risk_eval.EVAL_DIR / "embedding_dimension_study.json"
DECISION_RULE = (
    "Change EMBEDDING_DIMENSIONS only if a larger size gives strictly more top-3 hits than 64 on both the golden "
    "and the held-out set. If several sizes qualify, take the smallest."
)
HUB_KEY = "pd-server-room-flood"
STOPWORDS = frozenset(
    "a an and are as at be been but by can for from has have in is it its no not of on or so that the their there "
    "these this to was were which while who will with within".split()
)
HUB_METHOD = (
    "Diagnostic only, outside the pipeline: re-ranks the decided past risks for every expected-complete case in both "
    "sets with app.services.knowledge.local_embedding and cosine_similarity at the chosen size, on the same title and "
    "description text the pipeline embeds, once as built and once with common English stopwords removed from both sides."
)


def measure(dimensions: int) -> dict:
    original = knowledge.EMBEDDING_DIMENSIONS
    knowledge.EMBEDDING_DIMENSIONS = dimensions
    try:
        settings = Settings(llm_provider="openai", openai_api_key=None, anthropic_api_key=None)
        row: dict = {"dimensions": dimensions}
        for name, (case_path, _) in risk_eval.CASE_SETS.items():
            results = risk_eval.run_evaluation(settings, "fallback", case_path)
            top3_lists = [case["retrieved_past"] for case in results["cases"] if not case["needs_info"]]
            key, count = Counter(k for top3 in top3_lists for k in top3).most_common(1)[0]
            row[name] = {
                "past_decision_hit_rate_top3": results["metrics"]["past_decision_hit_rate_top3"],
                "misses": [c["id"] for c in results["cases"] if c["expected_similar_past"] and c["past_hit_rank"] is None],
                "most_retrieved_past_decision": {"key": key, "in_top3_lists": count, "complete_cases": len(top3_lists)},
            }
        return row
    finally:
        knowledge.EMBEDDING_DIMENSIONS = original


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _stopword_share(text: str) -> float:
    tokens = _tokens(text)
    return sum(token in STOPWORDS for token in tokens) / len(tokens)


def hub_diagnostic(dimensions: int) -> dict:
    past = risk_eval.load_json(risk_eval.PAST_DECISIONS_PATH)["decisions"]
    cases = [
        case
        for case_path, _ in risk_eval.CASE_SETS.values()
        for case in risk_eval.load_json(case_path)["cases"]
        if not case["expected_needs_info"]
    ]
    variants = {"as_built": lambda text: text, "stopwords_removed": lambda text: " ".join(t for t in _tokens(text) if t not in STOPWORDS)}
    report: dict = {"method": HUB_METHOD, "dimensions": dimensions, "cases": len(cases)}
    for name, transform in variants.items():
        past_vectors = {
            p["key"]: knowledge.local_embedding(transform(f"{p['title']} {p['description']}"), dimensions) for p in past
        }
        counts: Counter = Counter()
        for case in cases:
            query = knowledge.local_embedding(transform(f"{case['title']} {case['description']}"), dimensions)
            ranked = sorted(past_vectors, key=lambda key: knowledge.cosine_similarity(query, past_vectors[key]), reverse=True)
            counts.update(ranked[:3])
        key, count = counts.most_common(1)[0]
        report[name] = {f"{HUB_KEY}_in_top3_lists": counts[HUB_KEY], "most_retrieved": {"key": key, "in_top3_lists": count}}
    others = [_stopword_share(f"{p['title']} {p['description']}") for p in past if p["key"] != HUB_KEY]
    hub_text = next(f"{p['title']} {p['description']}" for p in past if p["key"] == HUB_KEY)
    report["stopword_share"] = {HUB_KEY: round(_stopword_share(hub_text), 2), "other_past_risks_mean": round(sum(others) / len(others), 2)}
    return report


def main() -> int:
    rows = [measure(dimensions) for dimensions in DIMENSIONS]
    baseline = rows[0]
    qualifying = [
        row["dimensions"]
        for row in rows[1:]
        if all(
            row[name]["past_decision_hit_rate_top3"]["hits"] > baseline[name]["past_decision_hit_rate_top3"]["hits"]
            for name in risk_eval.CASE_SETS
        )
    ]
    chosen = min(qualifying) if qualifying else baseline["dimensions"]
    study = {
        "decision_rule": DECISION_RULE,
        "rows": rows,
        "sizes_that_improve_both_sets": qualifying,
        "chosen_dimensions": chosen,
        "hub_diagnostic": hub_diagnostic(chosen),
    }
    OUT_PATH.write_text(json.dumps(study, indent=2) + "\n", encoding="utf-8")

    print(DECISION_RULE)
    print(f"{'dims':>5}  {'golden hits':>11}  {'holdout hits':>12}  most retrieved past decision (golden | holdout)")
    for row in rows:
        golden, holdout = row["golden"], row["holdout"]
        g, h = golden["past_decision_hit_rate_top3"], holdout["past_decision_hit_rate_top3"]
        gm, hm = golden["most_retrieved_past_decision"], holdout["most_retrieved_past_decision"]
        print(
            f"{row['dimensions']:>5}  {g['hits']:>5}/{g['total']:<5}  {h['hits']:>6}/{h['total']:<5}  "
            f"{gm['key']} {gm['in_top3_lists']}/{gm['complete_cases']} | {hm['key']} {hm['in_top3_lists']}/{hm['complete_cases']}"
        )
    print(f"sizes that improve both sets: {qualifying or 'none'}, chosen: {chosen}")
    hub = study["hub_diagnostic"]
    for name in ("as_built", "stopwords_removed"):
        print(
            f"hub diagnostic at {chosen}, {name}: {HUB_KEY} in {hub[name][f'{HUB_KEY}_in_top3_lists']}/{hub['cases']} "
            f"top-3 lists, most retrieved {hub[name]['most_retrieved']['key']} {hub[name]['most_retrieved']['in_top3_lists']}"
        )
    print(f"stopword share: {hub['stopword_share']}")
    print(f"Results written to {OUT_PATH}")
    return 0


if __name__ == "__main__":
    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING))
    sys.exit(main())
