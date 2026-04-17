"""002 source type rules table

Revision ID: 002_source_type_rules
Revises: 001_baseline
Create Date: 2026-04-18 00:00:00.000000

Adds the source_type_rule table for admin-managed dynamic source type
detection rules (S10 — Dynamic Source Type Categorization System).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002_source_type_rules"
down_revision: Union[str, None] = "001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source_type_rule",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("pattern", sa.String(500), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default=sa.text("100")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_type_rule_active_priority",
        "source_type_rule",
        ["is_active", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_type_rule_active_priority", table_name="source_type_rule")
    op.drop_table("source_type_rule")
