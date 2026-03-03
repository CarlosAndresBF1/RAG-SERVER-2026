"""Evaluation test suite for Odyssey RAG retrieval quality.

Measures Precision@5, Recall@10, MRR, content match rate, and gap
detection accuracy across 58+ domain questions.

Targets (from EVALUATION_SET.md §2):
  Precision@5   >= 0.70
  Recall@10     >= 0.80
  MRR           >= 0.75
  Content match <= 20% miss rate (>= 80% hit rate)
  Gap Accuracy  >= 0.60

Usage:
    # Requires live database + embeddings (Docker stack running):
    PYTHONPATH=src pytest tests/evaluation/ -v -m evaluation

    # Print a full metrics report:
    PYTHONPATH=src pytest tests/evaluation/ -v -m evaluation -s

IMPORTANT: These tests require a running PostgreSQL + pgvector database
populated by ``scripts/seed_initial_sources.py``.  They are skipped
automatically when no DATABASE_URL is reachable.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

import pytest

QUESTIONS_PATH = Path(__file__).parent / "evaluation_questions.json"


# ── Skip guard ────────────────────────────────────────────────────────────────

def _db_available() -> bool:
    """Return True when DATABASE_URL is set and asyncpg is importable."""
    if not os.environ.get("DATABASE_URL"):
        return False
    try:
        import asyncpg  # noqa: F401
        return True
    except ImportError:
        return False


pytestmark = pytest.mark.evaluation

_skip_no_db = pytest.mark.skipif(
    not _db_available(),
    reason="DATABASE_URL not set or asyncpg not installed — evaluation requires live DB",
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def questions() -> list[dict[str, Any]]:
    """Load evaluation questions from JSON file."""
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def retrieval_engine():
    """Real RetrievalEngine backed by the live database."""
    from odyssey_rag.retrieval.engine import RetrievalEngine
    return RetrievalEngine()


@pytest.fixture(scope="module")
def event_loop():
    """Module-scoped event loop for async evaluation tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _non_gap_questions(questions: list[dict]) -> list[dict]:
    """Return questions that are not gap-detection cases."""
    return [q for q in questions if not q.get("expect_gap", False)]


def _gap_questions(questions: list[dict]) -> list[dict]:
    return [q for q in questions if q.get("expect_gap", False)]


async def _search(engine, question: dict):
    """Run a retrieval search for the given question."""
    tool_context: dict[str, str] = dict(question.get("params", {}))
    return await engine.search(
        question["query"],
        tool_name=question.get("tool", "search"),
        tool_context=tool_context or None,
    )


# ── Metric Tests ──────────────────────────────────────────────────────────────

@_skip_no_db
class TestEvaluationMetrics:
    """Automated precision/recall/MRR evaluation against the question set."""

    def test_precision_at_5(self, questions, retrieval_engine, event_loop):
        """Average Precision@5 should be >= 0.70."""
        non_gap = _non_gap_questions(questions)
        precisions: list[float] = []

        for q in non_gap:
            if not q.get("expected_sources"):
                continue
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            top5 = response.evidence[:5]
            relevant = sum(
                1 for e in top5 if e.source_type in q["expected_sources"]
            )
            precisions.append(relevant / 5)

        avg = sum(precisions) / len(precisions) if precisions else 0.0
        print(f"\nPrecision@5: {avg:.3f} (target >= 0.70, n={len(precisions)})")
        assert avg >= 0.70, (
            f"Precision@5 = {avg:.3f} is below target 0.70 "
            f"(evaluated {len(precisions)} questions)"
        )

    def test_recall_at_10(self, questions, retrieval_engine, event_loop):
        """Average Recall@10 should be >= 0.80."""
        non_gap = _non_gap_questions(questions)
        recalls: list[float] = []

        for q in non_gap:
            expected = set(q.get("expected_sources", []))
            if not expected:
                continue
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            found = {e.source_type for e in response.evidence[:10]}
            recall = len(found & expected) / len(expected)
            recalls.append(recall)

        avg = sum(recalls) / len(recalls) if recalls else 0.0
        print(f"\nRecall@10: {avg:.3f} (target >= 0.80, n={len(recalls)})")
        assert avg >= 0.80, (
            f"Recall@10 = {avg:.3f} is below target 0.80 "
            f"(evaluated {len(recalls)} questions)"
        )

    def test_mrr(self, questions, retrieval_engine, event_loop):
        """Mean Reciprocal Rank should be >= 0.75."""
        non_gap = _non_gap_questions(questions)
        rrs: list[float] = []

        for q in non_gap:
            keywords = [kw.lower() for kw in q.get("expected_content", [])]
            if not keywords:
                continue
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            rr = 0.0
            for rank, e in enumerate(response.evidence, 1):
                text_lower = e.text.lower()
                if any(kw in text_lower for kw in keywords):
                    rr = 1.0 / rank
                    break
            rrs.append(rr)

        mrr = sum(rrs) / len(rrs) if rrs else 0.0
        print(f"\nMRR: {mrr:.3f} (target >= 0.75, n={len(rrs)})")
        assert mrr >= 0.75, (
            f"MRR = {mrr:.3f} is below target 0.75 "
            f"(evaluated {len(rrs)} questions)"
        )

    def test_content_match(self, questions, retrieval_engine, event_loop):
        """At least one expected keyword should appear in top-5 for >= 80% of questions."""
        non_gap = _non_gap_questions(questions)
        misses: list[str] = []

        for q in non_gap:
            keywords = [kw.lower() for kw in q.get("expected_content", [])]
            if not keywords:
                continue
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            top5_text = " ".join(e.text.lower() for e in response.evidence[:5])
            if not any(kw in top5_text for kw in keywords):
                misses.append(q["id"])

        evaluated = len([q for q in non_gap if q.get("expected_content")])
        miss_rate = len(misses) / evaluated if evaluated else 0.0
        print(
            f"\nContent match: {1 - miss_rate:.1%} hit rate "
            f"(target >= 80%, misses: {misses})"
        )
        assert miss_rate <= 0.20, (
            f"Content miss rate = {miss_rate:.0%} exceeds 20% limit. "
            f"Missing IDs: {misses}"
        )

    def test_gap_accuracy(self, questions, retrieval_engine, event_loop):
        """Gap questions should trigger at least one gap message >= 60% of the time."""
        gap_qs = _gap_questions(questions)
        if not gap_qs:
            pytest.skip("No gap questions in evaluation set")

        correct = 0
        for q in gap_qs:
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            if response.gaps:
                correct += 1

        accuracy = correct / len(gap_qs)
        print(f"\nGap accuracy: {accuracy:.1%} (target >= 60%, n={len(gap_qs)})")
        assert accuracy >= 0.60, (
            f"Gap accuracy = {accuracy:.1%} is below target 60%"
        )

    def test_source_coverage(self, questions, retrieval_engine, event_loop):
        """Every source type in expected_sources should be returned at least once."""
        all_expected = set()
        for q in questions:
            all_expected.update(q.get("expected_sources", []))

        found_types: set[str] = set()
        for q in questions:
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            found_types.update(e.source_type for e in response.evidence)

        missing = all_expected - found_types
        coverage = len(all_expected - missing) / len(all_expected) if all_expected else 1.0
        print(f"\nSource coverage: {coverage:.0%} (missing: {missing})")
        assert not missing, (
            f"Source types never appeared in any result: {missing}"
        )


# ── Per-category Tests ────────────────────────────────────────────────────────

@_skip_no_db
class TestCategoryPrecision:
    """Per-category precision to help identify weak areas."""

    def _precision_for_category(
        self, category: str, questions, retrieval_engine, event_loop
    ) -> float:
        cat_qs = [q for q in questions if q.get("category") == category and not q.get("expect_gap")]
        if not cat_qs:
            return 1.0
        precisions = []
        for q in cat_qs:
            if not q.get("expected_sources"):
                continue
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            top5 = response.evidence[:5]
            relevant = sum(1 for e in top5 if e.source_type in q["expected_sources"])
            precisions.append(relevant / 5)
        return sum(precisions) / len(precisions) if precisions else 0.0

    def test_find_message_type_category(self, questions, retrieval_engine, event_loop):
        p = self._precision_for_category("find_message_type", questions, retrieval_engine, event_loop)
        print(f"\nfind_message_type Precision@5: {p:.3f}")
        assert p >= 0.60, f"find_message_type precision {p:.3f} < 0.60"

    def test_find_business_rule_category(self, questions, retrieval_engine, event_loop):
        p = self._precision_for_category("find_business_rule", questions, retrieval_engine, event_loop)
        print(f"\nfind_business_rule Precision@5: {p:.3f}")
        assert p >= 0.60, f"find_business_rule precision {p:.3f} < 0.60"

    def test_find_module_category(self, questions, retrieval_engine, event_loop):
        p = self._precision_for_category("find_module", questions, retrieval_engine, event_loop)
        print(f"\nfind_module Precision@5: {p:.3f}")
        assert p >= 0.60, f"find_module precision {p:.3f} < 0.60"

    def test_find_error_category(self, questions, retrieval_engine, event_loop):
        p = self._precision_for_category("find_error", questions, retrieval_engine, event_loop)
        print(f"\nfind_error Precision@5: {p:.3f}")
        assert p >= 0.60, f"find_error precision {p:.3f} < 0.60"

    def test_search_category(self, questions, retrieval_engine, event_loop):
        p = self._precision_for_category("search", questions, retrieval_engine, event_loop)
        print(f"\nsearch Precision@5: {p:.3f}")
        assert p >= 0.50, f"search precision {p:.3f} < 0.50"


# ── Report Generator ──────────────────────────────────────────────────────────

@_skip_no_db
class TestEvaluationReport:
    """Generates a human-readable evaluation report (printed to stdout with -s)."""

    def test_generate_report(self, questions, retrieval_engine, event_loop):
        """Run all questions and print a summary report."""
        non_gap = _non_gap_questions(questions)

        precisions: list[float] = []
        recalls: list[float] = []
        rrs: list[float] = []
        misses: list[str] = []
        per_category: dict[str, list[float]] = {}

        for q in non_gap:
            response = event_loop.run_until_complete(_search(retrieval_engine, q))
            cat = q.get("category", "unknown")
            expected_sources = set(q.get("expected_sources", []))
            keywords = [kw.lower() for kw in q.get("expected_content", [])]

            # Precision@5
            if expected_sources:
                top5 = response.evidence[:5]
                p5 = sum(1 for e in top5 if e.source_type in expected_sources) / 5
                precisions.append(p5)
                per_category.setdefault(cat, []).append(p5)

                # Recall@10
                found = {e.source_type for e in response.evidence[:10]}
                recalls.append(len(found & expected_sources) / len(expected_sources))

            # MRR
            if keywords:
                rr = 0.0
                for rank, e in enumerate(response.evidence, 1):
                    if any(kw in e.text.lower() for kw in keywords):
                        rr = 1.0 / rank
                        break
                rrs.append(rr)

                # Content match
                top5_text = " ".join(e.text.lower() for e in response.evidence[:5])
                if not any(kw in top5_text for kw in keywords):
                    misses.append(q["id"])

        avg_p5 = sum(precisions) / len(precisions) if precisions else 0.0
        avg_r10 = sum(recalls) / len(recalls) if recalls else 0.0
        mrr = sum(rrs) / len(rrs) if rrs else 0.0
        miss_rate = len(misses) / len(non_gap) if non_gap else 0.0

        def _fmt(v: float, target: float) -> str:
            mark = "✓" if v >= target else "✗"
            return f"{v:.3f} (target >= {target}) {mark}"

        report = [
            "",
            "═" * 50,
            "ODYSSEY RAG — EVALUATION REPORT",
            f"Questions: {len(non_gap)} (+ {len(_gap_questions(questions))} gap)",
            "─" * 50,
            f"Precision@5:    {_fmt(avg_p5, 0.70)}",
            f"Recall@10:      {_fmt(avg_r10, 0.80)}",
            f"MRR:            {_fmt(mrr, 0.75)}",
            f"Content Match:  {_fmt(1 - miss_rate, 0.80)}",
            "─" * 50,
            "Per-category Precision@5:",
        ]
        for cat, vals in sorted(per_category.items()):
            avg = sum(vals) / len(vals)
            report.append(f"  {cat:<25} {avg:.3f}")

        if misses:
            report += ["─" * 50, f"Content misses ({len(misses)}): {', '.join(misses)}"]

        report.append("═" * 50)
        print("\n".join(report))

        # Soft assertion — report is always generated; fail only if catastrophically bad
        assert avg_p5 >= 0.50, f"Precision@5 = {avg_p5:.3f} is catastrophically low"
