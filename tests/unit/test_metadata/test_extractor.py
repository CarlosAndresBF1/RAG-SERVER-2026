"""Unit tests for MetadataExtractor."""

from __future__ import annotations

import pytest

from odyssey_rag.ingestion.chunkers.base import Chunk
from odyssey_rag.ingestion.metadata.extractor import (
    MESSAGE_TYPE_PATTERNS,
    ExtractedMetadata,
    MetadataExtractor,
)


def make_chunk(
    content: str,
    metadata: dict | None = None,
) -> Chunk:
    """Create a Chunk for testing."""
    return Chunk(
        content=content,
        token_count=len(content) // 4,
        metadata=metadata or {},
    )


class TestMetadataExtractor:
    """Tests for MetadataExtractor."""

    def setup_method(self) -> None:
        self.extractor = MetadataExtractor()

    # ── source_type ───────────────────────────────────────────────────────────

    def test_source_type_is_set(self) -> None:
        """source_type is always set from argument."""
        chunk = make_chunk("Some content")
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.source_type == "annex_b_spec"

    # ── message_type detection ────────────────────────────────────────────────

    def test_detect_pacs008_from_content(self) -> None:
        """Detects pacs.008 from explicit mention in content."""
        chunk = make_chunk("This section covers pacs.008 credit transfers.")
        meta = self.extractor.extract(chunk, "generic_text")
        assert meta.message_type == "pacs.008"

    def test_detect_pacs002_from_content(self) -> None:
        """Detects pacs.002 from content keyword."""
        chunk = make_chunk("The FIToFIPmtStsRpt message is used for status reporting.")
        meta = self.extractor.extract(chunk, "generic_text")
        assert meta.message_type == "pacs.002"

    def test_detect_camt056_from_content(self) -> None:
        """Detects camt.056 from content pattern."""
        chunk = make_chunk("FIToFIPmtCxlReq is used to recall a payment.")
        meta = self.extractor.extract(chunk, "generic_text")
        assert meta.message_type == "camt.056"

    def test_detect_pain001_from_content(self) -> None:
        """Detects pain.001 from pain.001 mention."""
        chunk = make_chunk("pain.001 is the customer credit transfer initiation.")
        meta = self.extractor.extract(chunk, "generic_text")
        assert meta.message_type == "pain.001"

    def test_no_message_type_returns_none(self) -> None:
        """Content with no ISO pattern returns None for message_type."""
        chunk = make_chunk("Hello world, this is unrelated content.")
        meta = self.extractor.extract(chunk, "generic_text")
        assert meta.message_type is None

    def test_hint_overrides_detection(self) -> None:
        """Parser-provided hint takes priority over content detection."""
        chunk = make_chunk(
            "This content mentions pacs.002.",
            metadata={"message_type": "pacs.008"},
        )
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.message_type == "pacs.008"

    # ── ISO version detection ─────────────────────────────────────────────────

    def test_detect_iso_version(self) -> None:
        """Detects full ISO version string from content."""
        chunk = make_chunk(
            "This covers the pacs.008.001.12 specification."
        )
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.iso_version == "pacs.008.001.12"

    def test_iso_version_none_when_absent(self) -> None:
        """iso_version is None when no version string is present."""
        chunk = make_chunk("Just pacs.008 mentions here.")
        meta = self.extractor.extract(chunk, "generic_text")
        # message_type found, but no version
        assert meta.iso_version is None

    # ── Annex B specific ──────────────────────────────────────────────────────

    def test_extract_rule_status_mandatory(self) -> None:
        """Extracts M (Mandatory) rule status from Annex B table row."""
        chunk = make_chunk("| GrpHdr/MsgId | <MsgId> | [1..1] | M | Max35Text | ID |")
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.rule_status == "M"

    def test_extract_rule_status_optional(self) -> None:
        """Extracts O (Optional) rule status from Annex B table row."""
        chunk = make_chunk("| CdtTrfTxInf/Purp | <Purp> | [0..1] | O | Purpose2Choice | Purpose |")
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.rule_status == "O"

    def test_extract_data_type(self) -> None:
        """Extracts data type from Annex B table content."""
        chunk = make_chunk("| GrpHdr/MsgId | <MsgId> | [1..1] | M | Max35Text | Identifier |")
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.data_type == "Max35Text"

    def test_extract_xpath_from_table(self) -> None:
        """Extracts XPath from first column of Annex B table row."""
        chunk = make_chunk("| GrpHdr/MsgId | <MsgId> | [1..1] | M | Max35Text | ID |")
        meta = self.extractor.extract(chunk, "annex_b_spec")
        assert meta.field_xpath == "GrpHdr/MsgId"

    def test_annex_b_fields_not_extracted_for_other_types(self) -> None:
        """field_xpath is not extracted for non-Annex B source types."""
        chunk = make_chunk("| GrpHdr/MsgId | stuff |")
        meta = self.extractor.extract(chunk, "php_code")
        # No annex_b extraction for php_code
        assert meta.field_xpath is None

    # ── PHP domain ────────────────────────────────────────────────────────────

    def test_php_hints_propagated(self) -> None:
        """PHP class/symbol/module_path hints are propagated to metadata."""
        chunk = make_chunk(
            "public function buildDocument(): void {}",
            metadata={
                "php_class": "Pacs008",
                "php_symbol": "buildDocument",
                "module_path": "Bimpay/Messages/Pacs008.php",
            },
        )
        meta = self.extractor.extract(chunk, "php_code")
        assert meta.php_class == "Pacs008"
        assert meta.php_symbol == "buildDocument"
        assert meta.module_path == "Bimpay/Messages/Pacs008.php"

    # ── to_dict ───────────────────────────────────────────────────────────────

    def test_to_dict_excludes_none_values(self) -> None:
        """to_dict() omits fields that are None."""
        meta = ExtractedMetadata(source_type="generic_text")
        d = meta.to_dict()
        assert "message_type" not in d
        assert "source_type" in d

    def test_to_dict_includes_set_values(self) -> None:
        """to_dict() includes all non-None fields."""
        meta = ExtractedMetadata(
            source_type="annex_b_spec",
            message_type="pacs.008",
            rule_status="M",
        )
        d = meta.to_dict()
        assert d["source_type"] == "annex_b_spec"
        assert d["message_type"] == "pacs.008"
        assert d["rule_status"] == "M"


class TestMessageTypePatterns:
    """Verify MESSAGE_TYPE_PATTERNS covers all 10 message types."""

    def test_all_ten_types_defined(self) -> None:
        """MESSAGE_TYPE_PATTERNS defines exactly 10 message types."""
        assert len(MESSAGE_TYPE_PATTERNS) == 10

    @pytest.mark.parametrize("msg_type", [
        "pacs.008", "pacs.002", "pacs.004", "pacs.028",
        "camt.056", "camt.029",
        "pain.001", "pain.002", "pain.013", "pain.014",
    ])
    def test_pattern_exists(self, msg_type: str) -> None:
        """Each of the 10 message types has at least 2 patterns."""
        assert msg_type in MESSAGE_TYPE_PATTERNS
        assert len(MESSAGE_TYPE_PATTERNS[msg_type]) >= 2
