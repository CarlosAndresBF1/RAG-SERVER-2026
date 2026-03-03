"""Unit tests for PostmanParser."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from odyssey_rag.ingestion.parsers.postman import PostmanParser

FIXTURES = Path(__file__).parent.parent.parent / "fixtures"


class TestPostmanParser:
    """Tests for PostmanParser."""

    def setup_method(self) -> None:
        self.parser = PostmanParser()

    def test_supported_extensions(self) -> None:
        """supported_extensions returns .json."""
        exts = self.parser.supported_extensions()
        assert ".json" in exts

    def test_parse_sample_returns_sections(self) -> None:
        """Parsing the sample Postman collection returns multiple sections."""
        sections = self.parser.parse(
            str(FIXTURES / "sample_postman.postman_collection.json")
        )
        assert len(sections) >= 2

    def test_parse_method_in_content(self) -> None:
        """HTTP method (POST/GET) appears in section content."""
        sections = self.parser.parse(
            str(FIXTURES / "sample_postman.postman_collection.json")
        )
        methods_in_content = [
            s for s in sections
            if "POST" in s.content or "GET" in s.content
        ]
        assert len(methods_in_content) >= 1

    def test_parse_request_method_metadata(self) -> None:
        """request_method metadata is set on each section."""
        sections = self.parser.parse(
            str(FIXTURES / "sample_postman.postman_collection.json")
        )
        for s in sections:
            assert "request_method" in s.metadata

    def test_parse_message_type_detected(self) -> None:
        """message_type metadata is detected from URLs and bodies."""
        sections = self.parser.parse(
            str(FIXTURES / "sample_postman.postman_collection.json")
        )
        types = {
            s.metadata.get("message_type") for s in sections
            if s.metadata.get("message_type")
        }
        assert len(types) > 0

    def test_parse_url_in_content(self) -> None:
        """URL appears in section content."""
        sections = self.parser.parse(
            str(FIXTURES / "sample_postman.postman_collection.json")
        )
        urls_present = [s for s in sections if "api/v1" in s.content]
        assert len(urls_present) >= 1

    def test_parse_invalid_json_returns_error_section(self, tmp_path: Path) -> None:
        """Invalid JSON returns a single postman_parse_error section."""
        bad = tmp_path / "bad.postman_collection.json"
        bad.write_text("{not valid json}")
        sections = self.parser.parse(str(bad))
        assert len(sections) == 1
        assert sections[0].section == "postman_parse_error"

    def test_parse_content_not_empty(self) -> None:
        """All sections have non-empty content."""
        sections = self.parser.parse(
            str(FIXTURES / "sample_postman.postman_collection.json")
        )
        for s in sections:
            assert s.content.strip() != ""

    def test_parse_inline_collection(self, tmp_path: Path) -> None:
        """Parser handles a minimal collection with one request."""
        collection = {
            "info": {"name": "Test"},
            "item": [
                {
                    "name": "Health Check",
                    "request": {
                        "method": "GET",
                        "header": [],
                        "url": {"raw": "http://localhost/health"},
                    },
                    "response": [],
                }
            ],
        }
        f = tmp_path / "minimal.postman_collection.json"
        f.write_text(json.dumps(collection))
        sections = self.parser.parse(str(f))
        assert len(sections) == 1
        assert "GET" in sections[0].content
        assert "health" in sections[0].content.lower()
