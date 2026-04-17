"""Unit tests for the dynamic source type categorization system (S10).

Tests the categorizer module, the updated detect_source_type() in pipeline.py,
and the categories API endpoints.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from odyssey_rag.ingestion.categorizer import (
    CONTENT_KEYWORDS,
    CachedRule,
    SourceTypeCategorizer,
    _keyword_heuristic,
    get_categorizer,
)
from odyssey_rag.ingestion.pipeline import SOURCE_TYPE_RULES, detect_source_type


# ── Hardcoded rules regression ───────────────────────────────────────────────


class TestHardcodedRulesRegression:
    """Ensure all existing regex rules still produce correct source types."""

    @pytest.mark.parametrize(
        "filename, expected",
        [
            ("IPS_Annex_B_v2.md", "annex_b_spec"),
            ("BIMPAY_TECHNICAL_GUIDE.md", "tech_doc"),
            ("BIMPAY_INFRASTRUCTURE_setup.md", "tech_doc"),
            ("CLAUDE.md", "claude_context"),
            ("Annex_A_reference.md", "annex_a_spec"),
            ("annex_c_spec.md", "annex_c_spec"),
            ("alias_management.txt", "alias_doc"),
            ("QR_code_flows.md", "qr_doc"),
            ("codigo_qr.md", "qr_doc"),
            ("home_banking_api.md", "banking_doc"),
            ("banca_electronica.md", "banking_doc"),
            ("integration_guide.md", "integration_doc"),
            ("Paysett_API.md", "paysett_doc"),
            ("PAYSSET_flow.md", "paysett_doc"),
            ("blite_setup.md", "blite_doc"),
            ("blossom_connector.md", "blite_doc"),
            ("runbook_deploy.md", "runbook"),
            ("ops_guide.md", "runbook"),
            ("architecture_overview.md", "architecture_doc"),
            ("system_design.md", "architecture_doc"),
            ("handler.php", "php_code"),
            ("example.xml", "xml_example"),
            ("api.postman_collection.json", "postman_collection"),
            ("report.pdf", "pdf_doc"),
            ("report.docx", "word_doc"),
            ("README.md", "generic_text"),
            ("notes.txt", "generic_text"),
        ],
    )
    def test_hardcoded_rule_detection(self, filename: str, expected: str) -> None:
        """Each hardcoded rule should still produce the correct source type."""
        categorizer = SourceTypeCategorizer()
        result = categorizer.detect_source_type_sync(filename)
        assert result == expected, f"{filename!r} → {result!r}, expected {expected!r}"


# ── Override priority ────────────────────────────────────────────────────────


class TestOverridePriority:
    """API override must always take highest priority."""

    def test_override_takes_precedence(self) -> None:
        categorizer = SourceTypeCategorizer()
        result = categorizer.detect_source_type_sync(
            "IPS_Annex_B_v2.md",
            overrides={"source_type": "custom_override"},
        )
        assert result == "custom_override"

    def test_override_with_unknown_file(self) -> None:
        categorizer = SourceTypeCategorizer()
        result = categorizer.detect_source_type_sync(
            "completely_unknown_file.xyz",
            overrides={"source_type": "my_type"},
        )
        assert result == "my_type"

    def test_empty_overrides_ignored(self) -> None:
        categorizer = SourceTypeCategorizer()
        result = categorizer.detect_source_type_sync(
            "README.md",
            overrides={},
        )
        assert result == "generic_text"

    def test_none_overrides_ignored(self) -> None:
        categorizer = SourceTypeCategorizer()
        result = categorizer.detect_source_type_sync("README.md", overrides=None)
        assert result == "generic_text"


# ── DB custom rules (cached) ────────────────────────────────────────────────


class TestDBCustomRules:
    """DB-backed custom rules should be applied after hardcoded rules."""

    def test_db_rule_matches_unknown_file(self) -> None:
        categorizer = SourceTypeCategorizer()
        # Inject cached rule
        categorizer._cached_rules = [
            CachedRule(pattern=r"(?i)mimics", source_type="mimics_doc", priority=50),
        ]
        result = categorizer.detect_source_type_sync("Mimics_API_Reference.pdf")
        # .pdf matches hardcoded "pdf_doc" first — verify chain order
        assert result == "pdf_doc"

    def test_db_rule_matches_when_no_hardcoded(self) -> None:
        categorizer = SourceTypeCategorizer()
        categorizer._cached_rules = [
            CachedRule(pattern=r"(?i)mimics.*\.yaml$", source_type="mimics_config", priority=50),
        ]
        result = categorizer.detect_source_type_sync("Mimics_setup_v2.yaml")
        assert result == "mimics_config"

    def test_db_rules_ordered_by_priority(self) -> None:
        categorizer = SourceTypeCategorizer()
        categorizer._cached_rules = [
            CachedRule(pattern=r"(?i)special", source_type="low_priority", priority=200),
            CachedRule(pattern=r"(?i)special", source_type="high_priority", priority=10),
        ]
        # Cache is list order; the higher-priority (lower number) should be first
        # since refresh sorts by priority. Simulate sorted order:
        categorizer._cached_rules.sort(key=lambda r: r.priority)
        result = categorizer.detect_source_type_sync("special_doc.yaml")
        assert result == "high_priority"

    def test_invalid_db_regex_skipped(self) -> None:
        categorizer = SourceTypeCategorizer()
        categorizer._cached_rules = [
            CachedRule(pattern=r"[invalid", source_type="bad_rule", priority=50),
            CachedRule(pattern=r"(?i)good_pattern", source_type="good_rule", priority=60),
        ]
        result = categorizer.detect_source_type_sync("good_pattern.yaml")
        assert result == "good_rule"


# ── Content keyword heuristic ────────────────────────────────────────────────


class TestKeywordHeuristic:
    """Keyword heuristic catches new integration names in filenames."""

    def test_mimics_keyword(self) -> None:
        result = _keyword_heuristic("Mimics_API_Reference.yaml")
        assert result == "mimics_doc"

    def test_architecture_keyword(self) -> None:
        result = _keyword_heuristic("system_architecture_v2.yaml")
        assert result == "architecture_doc"

    def test_runbook_keyword(self) -> None:
        result = _keyword_heuristic("deploy_runbook.yaml")
        assert result == "runbook"

    def test_case_insensitive(self) -> None:
        result = _keyword_heuristic("BIMPAY_flows.yaml")
        assert result == "tech_doc"

    def test_no_match_returns_none(self) -> None:
        result = _keyword_heuristic("completely_unrecognized_xyz.yaml")
        assert result is None

    def test_full_chain_hits_keyword_heuristic(self) -> None:
        """When no regex or DB rule matches, keyword heuristic is used."""
        categorizer = SourceTypeCategorizer()
        # .yaml doesn't match any hardcoded rule, no DB rules cached
        result = categorizer.detect_source_type_sync("Mimics_setup_guide.yaml")
        assert result == "mimics_doc"

    def test_full_chain_falls_to_generic(self) -> None:
        """Completely unknown files fall through to generic_text."""
        categorizer = SourceTypeCategorizer()
        result = categorizer.detect_source_type_sync("xyzzy_foobar.yaml")
        assert result == "generic_text"


# ── detect_source_type() in pipeline.py ──────────────────────────────────────


class TestPipelineDetectSourceType:
    """Test the pipeline's detect_source_type() wrapper."""

    def test_still_detects_hardcoded(self) -> None:
        assert detect_source_type("IPS_Annex_B_v2.md") == "annex_b_spec"

    def test_override_works(self) -> None:
        assert (
            detect_source_type("any_file.md", overrides={"source_type": "custom"})
            == "custom"
        )

    def test_unknown_file_gets_generic(self) -> None:
        assert detect_source_type("unknown.yaml") == "generic_text"


# ── Async detection ──────────────────────────────────────────────────────────


class TestAsyncDetection:
    """Test the async interface of the categorizer."""

    @pytest.mark.asyncio
    async def test_async_detection_basic(self) -> None:
        categorizer = SourceTypeCategorizer()
        # Pre-warm cache to avoid DB hit
        categorizer._last_refresh = 999999999999.0
        result = await categorizer.detect_source_type_async("IPS_Annex_B_v2.md")
        assert result == "annex_b_spec"

    @pytest.mark.asyncio
    async def test_async_detection_with_override(self) -> None:
        categorizer = SourceTypeCategorizer()
        categorizer._last_refresh = 999999999999.0
        result = await categorizer.detect_source_type_async(
            "any.md", overrides={"source_type": "forced"}
        )
        assert result == "forced"


# ── Suggestion logic (mocked) ───────────────────────────────────────────────


class TestSuggestionLogic:
    """Test the suggest_rules repository method with mocked DB."""

    @pytest.mark.asyncio
    async def test_suggest_rules_returns_candidates(self) -> None:
        """suggest_rules() should return source types with ≥3 docs and no rule."""
        from odyssey_rag.db.repositories.source_type_rules import SourceTypeRuleRepository

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(source_type="custom_type_a", doc_count=5),
            MagicMock(source_type="custom_type_b", doc_count=3),
        ]
        mock_session.execute = AsyncMock(return_value=mock_result)

        repo = SourceTypeRuleRepository(mock_session)
        suggestions = await repo.suggest_rules()

        assert len(suggestions) == 2
        assert suggestions[0]["source_type"] == "custom_type_a"
        assert suggestions[0]["doc_count"] == 5


# ── API endpoint tests (mocked DB) ──────────────────────────────────────────


class TestCategoryAPIEndpoints:
    """Test the categories router with mocked DB sessions."""

    @pytest.mark.asyncio
    async def test_detect_endpoint(self) -> None:
        """POST /categories/detect returns correct source type."""
        from fastapi.testclient import TestClient

        from odyssey_rag.api.main import create_app

        app = create_app()
        client = TestClient(app)

        with patch("odyssey_rag.api.auth.verify_api_key", return_value="test-key"):
            response = client.post(
                "/api/v1/categories/detect",
                json={"filename": "IPS_Annex_B_spec.md"},
                headers={"X-API-Key": "test"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["source_type"] == "annex_b_spec"

    @pytest.mark.asyncio
    async def test_list_categories_endpoint(self) -> None:
        """GET /categories returns all source types."""
        from fastapi.testclient import TestClient

        from odyssey_rag.api.main import create_app

        app = create_app()
        client = TestClient(app)

        with (
            patch("odyssey_rag.api.auth.verify_api_key", return_value="test-key"),
            patch(
                "odyssey_rag.api.routes.categories.db_session",
            ) as mock_db,
        ):
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)

            response = client.get(
                "/api/v1/categories",
                headers={"X-API-Key": "test"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] > 0
        # Should include at least some hardcoded types
        types = [item["source_type"] for item in data["items"]]
        assert "annex_b_spec" in types
        assert "generic_text" in types


# ── Cache refresh ────────────────────────────────────────────────────────────


class TestCacheRefresh:
    """Test cache management behaviour."""

    def test_cache_starts_empty(self) -> None:
        categorizer = SourceTypeCategorizer()
        assert categorizer._get_cached_rules() == []

    def test_cache_age_infinite_when_not_refreshed(self) -> None:
        categorizer = SourceTypeCategorizer()
        assert categorizer.cache_age_seconds == float("inf")

    @pytest.mark.asyncio
    async def test_refresh_cache_loads_rules(self) -> None:
        """Mocked DB refresh populates the in-memory cache."""
        categorizer = SourceTypeCategorizer()

        mock_rule = MagicMock()
        mock_rule.pattern = r"(?i)newtype"
        mock_rule.source_type = "new_type"
        mock_rule.priority = 50

        with patch(
            "odyssey_rag.db.session.db_session",
        ) as mock_db:
            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=False)
            mock_db.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_rule]
            mock_session.execute = AsyncMock(return_value=mock_result)

            count = await categorizer.refresh_cache()

        assert count == 1
        rules = categorizer._get_cached_rules()
        assert len(rules) == 1
        assert rules[0].source_type == "new_type"


# ── SOURCE_TYPE_RULES integrity ──────────────────────────────────────────────


class TestSourceTypeRulesIntegrity:
    """Verify SOURCE_TYPE_RULES list has not been accidentally broken."""

    def test_rules_list_not_empty(self) -> None:
        assert len(SOURCE_TYPE_RULES) >= 18

    def test_all_rules_are_tuples(self) -> None:
        for rule in SOURCE_TYPE_RULES:
            assert isinstance(rule, tuple)
            assert len(rule) == 2

    def test_all_patterns_compile(self) -> None:
        import re

        for pattern, _st in SOURCE_TYPE_RULES:
            re.compile(pattern)  # should not raise

    def test_generic_text_is_last(self) -> None:
        """generic_text catch-all should be the last rule."""
        _pattern, last_type = SOURCE_TYPE_RULES[-1]
        assert last_type == "generic_text"
