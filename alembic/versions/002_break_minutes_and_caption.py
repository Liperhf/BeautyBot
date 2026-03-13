"""Add break_minutes to schedule_templates; increase gallery caption to 500

Revision ID: 002
Revises: 001
Create Date: 2026-03-13
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "schedule_templates",
        sa.Column("break_minutes", sa.Integer, server_default="0", nullable=False),
    )
    op.alter_column(
        "gallery_photos",
        "caption",
        type_=sa.String(500),
        existing_type=sa.String(200),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "gallery_photos",
        "caption",
        type_=sa.String(200),
        existing_type=sa.String(500),
        existing_nullable=True,
    )
    op.drop_column("schedule_templates", "break_minutes")
