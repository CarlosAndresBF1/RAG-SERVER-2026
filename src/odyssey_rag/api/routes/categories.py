"""Category management endpoints — source type taxonomy & custom rules.

Provides CRUD for admin-managed detection rules and introspection of the
full source type taxonomy (hardcoded + custom + keyword heuristic).
"""

from __future__ import annotations

import re
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response

from odyssey_rag.api.auth import verify_api_key
from odyssey_rag.api.schemas import (
    CategoryDetectRequest,
    CategoryDetectResponse,
    CategoryListResponse,
    CategoryRuleCreate,
    CategoryRuleResponse,
    CategoryRuleUpdate,
    CategorySuggestionResponse,
)
from odyssey_rag.db.models import SourceTypeRule
from odyssey_rag.db.repositories.source_type_rules import SourceTypeRuleRepository
from odyssey_rag.db.session import db_session
from odyssey_rag.ingestion.categorizer import get_categorizer
from odyssey_rag.ingestion.pipeline import SOURCE_TYPE_RULES

logger = structlog.get_logger(__name__)
router = APIRouter(tags=["categories"])


# ── GET /categories — list all source types ──────────────────────────────────


@router.get(
    "/categories",
    response_model=CategoryListResponse,
    summary="List all known source types",
    dependencies=[Depends(verify_api_key)],
)
async def list_categories() -> CategoryListResponse:
    """Return all source types from hardcoded rules, DB rules, and keywords."""
    # Collect from hardcoded rules
    hardcoded = []
    seen: set[str] = set()
    for _pattern, st in SOURCE_TYPE_RULES:
        if st not in seen:
            hardcoded.append({"source_type": st, "origin": "hardcoded"})
            seen.add(st)

    # Collect from DB rules
    custom = []
    async with db_session() as session:
        repo = SourceTypeRuleRepository(session)
        db_rules = await repo.list_active()
        for rule in db_rules:
            if rule.source_type not in seen:
                custom.append({"source_type": rule.source_type, "origin": "custom"})
                seen.add(rule.source_type)

    # Collect from keyword heuristic
    from odyssey_rag.ingestion.categorizer import CONTENT_KEYWORDS

    keywords = []
    for _kw, st in CONTENT_KEYWORDS.items():
        if st not in seen:
            keywords.append({"source_type": st, "origin": "keyword"})
            seen.add(st)

    all_types = hardcoded + custom + keywords
    return CategoryListResponse(
        items=all_types,
        total=len(all_types),
    )


# ── GET /categories/rules — list custom DB rules ────────────────────────────


@router.get(
    "/categories/rules",
    response_model=list[CategoryRuleResponse],
    summary="List custom detection rules",
    dependencies=[Depends(verify_api_key)],
)
async def list_rules() -> list[CategoryRuleResponse]:
    """Return all custom rules (including inactive) from the database."""
    async with db_session() as session:
        repo = SourceTypeRuleRepository(session)
        rules = await repo.list_all()
    return [_rule_to_response(r) for r in rules]


# ── POST /categories/rules — create a new custom rule ───────────────────────


@router.post(
    "/categories/rules",
    response_model=CategoryRuleResponse,
    status_code=201,
    summary="Create a custom detection rule",
    dependencies=[Depends(verify_api_key)],
)
async def create_rule(body: CategoryRuleCreate) -> CategoryRuleResponse:
    """Create a new admin-managed source type detection rule."""
    # Validate regex
    try:
        re.compile(body.pattern)
    except re.error as exc:
        raise HTTPException(status_code=422, detail=f"Invalid regex: {exc}") from exc

    async with db_session() as session:
        repo = SourceTypeRuleRepository(session)
        rule = await repo.create(
            pattern=body.pattern,
            source_type=body.source_type,
            description=body.description,
            priority=body.priority,
        )

    # Refresh categorizer cache after creating a rule
    categorizer = get_categorizer()
    await categorizer.refresh_cache()

    return _rule_to_response(rule)


# ── PUT /categories/rules/{id} — update a rule ──────────────────────────────


@router.put(
    "/categories/rules/{rule_id}",
    response_model=CategoryRuleResponse,
    summary="Update a custom detection rule",
    dependencies=[Depends(verify_api_key)],
)
async def update_rule(rule_id: uuid.UUID, body: CategoryRuleUpdate) -> CategoryRuleResponse:
    """Update an existing custom detection rule."""
    if body.pattern is not None:
        try:
            re.compile(body.pattern)
        except re.error as exc:
            raise HTTPException(status_code=422, detail=f"Invalid regex: {exc}") from exc

    async with db_session() as session:
        repo = SourceTypeRuleRepository(session)
        rule = await repo.update(
            rule_id,
            pattern=body.pattern,
            source_type=body.source_type,
            description=body.description,
            priority=body.priority,
        )
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    categorizer = get_categorizer()
    await categorizer.refresh_cache()

    return _rule_to_response(rule)


# ── DELETE /categories/rules/{id} — soft-delete ─────────────────────────────


@router.delete(
    "/categories/rules/{rule_id}",
    status_code=204,
    response_class=Response,
    summary="Soft-delete a custom detection rule",
    dependencies=[Depends(verify_api_key)],
)
async def delete_rule(rule_id: uuid.UUID):
    """Soft-delete a rule (set is_active=False)."""
    async with db_session() as session:
        repo = SourceTypeRuleRepository(session)
        deleted = await repo.delete(rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Rule not found")

    categorizer = get_categorizer()
    await categorizer.refresh_cache()
    return Response(status_code=204)


# ── GET /categories/suggestions — auto-suggest rules ────────────────────────


@router.get(
    "/categories/suggestions",
    response_model=list[CategorySuggestionResponse],
    summary="Auto-suggest rules from override patterns",
    dependencies=[Depends(verify_api_key)],
)
async def suggest_rules() -> list[CategorySuggestionResponse]:
    """Suggest new rules based on frequently-overridden source types."""
    async with db_session() as session:
        repo = SourceTypeRuleRepository(session)
        suggestions = await repo.suggest_rules()
    return [
        CategorySuggestionResponse(
            source_type=s["source_type"],
            doc_count=s["doc_count"],
        )
        for s in suggestions
    ]


# ── POST /categories/detect — test detection ────────────────────────────────


@router.post(
    "/categories/detect",
    response_model=CategoryDetectResponse,
    summary="Test source type detection for a filename",
    dependencies=[Depends(verify_api_key)],
)
async def detect_category(body: CategoryDetectRequest) -> CategoryDetectResponse:
    """Submit a filename and get the detected source type."""
    categorizer = get_categorizer()
    detected = await categorizer.detect_source_type_async(body.filename)
    return CategoryDetectResponse(
        filename=body.filename,
        source_type=detected,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────


def _rule_to_response(rule: SourceTypeRule) -> CategoryRuleResponse:
    return CategoryRuleResponse(
        id=str(rule.id),
        pattern=rule.pattern,
        source_type=rule.source_type,
        description=rule.description,
        priority=rule.priority,
        is_active=rule.is_active,
        created_by=rule.created_by,
        created_at=rule.created_at.isoformat() if rule.created_at else None,
        updated_at=rule.updated_at.isoformat() if rule.updated_at else None,
    )
