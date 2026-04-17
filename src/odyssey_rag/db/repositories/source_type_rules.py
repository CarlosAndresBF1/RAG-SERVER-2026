"""Repository for SourceTypeRule CRUD operations.

Provides listing, creation, update, soft-delete, and suggestion queries
for the ``source_type_rule`` table.
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from odyssey_rag.db.models import Document, SourceTypeRule

logger = structlog.get_logger(__name__)


class SourceTypeRuleRepository:
    """Data access layer for the SourceTypeRule table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_active(self) -> list[SourceTypeRule]:
        """Return all active rules ordered by priority (ascending)."""
        stmt = (
            select(SourceTypeRule)
            .where(SourceTypeRule.is_active.is_(True))
            .order_by(SourceTypeRule.priority.asc(), SourceTypeRule.created_at.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[SourceTypeRule]:
        """Return all rules (including inactive) ordered by priority."""
        stmt = select(SourceTypeRule).order_by(
            SourceTypeRule.priority.asc(), SourceTypeRule.created_at.asc()
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, rule_id: uuid.UUID) -> SourceTypeRule | None:
        """Fetch a single rule by primary key."""
        stmt = select(SourceTypeRule).where(SourceTypeRule.id == rule_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        pattern: str,
        source_type: str,
        description: str | None = None,
        priority: int = 100,
        created_by: str | None = None,
    ) -> SourceTypeRule:
        """Insert a new custom detection rule."""
        rule = SourceTypeRule(
            pattern=pattern,
            source_type=source_type,
            description=description,
            priority=priority,
            created_by=created_by,
        )
        self._session.add(rule)
        await self._session.flush()
        logger.info(
            "source_type_rule.created",
            id=str(rule.id),
            pattern=pattern,
            source_type=source_type,
        )
        return rule

    async def update(self, rule_id: uuid.UUID, **fields: Any) -> SourceTypeRule | None:
        """Update fields on an existing rule.

        Returns the updated rule, or None if not found.
        """
        allowed = {"pattern", "source_type", "description", "priority", "is_active"}
        filtered = {k: v for k, v in fields.items() if k in allowed and v is not None}
        if not filtered:
            return await self.get_by_id(rule_id)

        stmt = (
            update(SourceTypeRule)
            .where(SourceTypeRule.id == rule_id)
            .values(**filtered)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("source_type_rule.updated", id=str(rule_id), fields=list(filtered.keys()))
        return await self.get_by_id(rule_id)

    async def delete(self, rule_id: uuid.UUID) -> bool:
        """Soft-delete a rule by setting is_active=False.

        Returns True if the rule existed and was deactivated.
        """
        rule = await self.get_by_id(rule_id)
        if rule is None:
            return False
        stmt = (
            update(SourceTypeRule)
            .where(SourceTypeRule.id == rule_id)
            .values(is_active=False)
        )
        await self._session.execute(stmt)
        await self._session.flush()
        logger.info("source_type_rule.deleted", id=str(rule_id))
        return True

    async def find_by_source_type(self, source_type: str) -> list[SourceTypeRule]:
        """Find all rules matching a given source_type value."""
        stmt = (
            select(SourceTypeRule)
            .where(SourceTypeRule.source_type == source_type)
            .order_by(SourceTypeRule.priority.asc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def suggest_rules(self) -> list[dict[str, Any]]:
        """Suggest rules for source_types used via override but without DB rules.

        Looks for source_types in the document table that appear ≥3 times
        and have no corresponding active SourceTypeRule.
        """
        # Subquery: active rule source types
        active_types = (
            select(SourceTypeRule.source_type)
            .where(SourceTypeRule.is_active.is_(True))
            .scalar_subquery()
        )

        stmt = (
            select(
                Document.source_type,
                func.count(Document.id).label("doc_count"),
            )
            .where(Document.is_current.is_(True))
            .where(Document.source_type.notin_(active_types))
            .group_by(Document.source_type)
            .having(func.count(Document.id) >= 3)
            .order_by(func.count(Document.id).desc())
        )
        result = await self._session.execute(stmt)
        return [
            {"source_type": row.source_type, "doc_count": row.doc_count}
            for row in result.all()
        ]
