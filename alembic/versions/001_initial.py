"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-12

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "masters",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("name", sa.String(100)),
        sa.Column("about_text", sa.Text),
        sa.Column("photo_file_id", sa.String(200)),
        sa.Column("contact_phone", sa.String(20)),
        sa.Column("contact_instagram", sa.String(100)),
        sa.Column("contact_address", sa.Text),
        sa.Column("timezone", sa.String(50), server_default="Europe/Minsk"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )
    op.create_table(
        "service_categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("master_id", sa.Integer, sa.ForeignKey("masters.id"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )
    op.create_table(
        "services",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("category_id", sa.Integer, sa.ForeignKey("service_categories.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
    )
    op.create_table(
        "schedule_templates",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("master_id", sa.Integer, sa.ForeignKey("masters.id"), nullable=False),
        sa.Column("day_of_week", sa.SmallInteger, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("slot_interval_minutes", sa.Integer, server_default="30"),
        sa.Column("is_working", sa.Boolean, server_default="true"),
    )
    op.create_table(
        "schedule_exceptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("master_id", sa.Integer, sa.ForeignKey("masters.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("is_day_off", sa.Boolean, server_default="false"),
        sa.Column("start_time", sa.Time),
        sa.Column("end_time", sa.Time),
        sa.Column("reason", sa.String(200)),
    )
    op.create_table(
        "clients",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("telegram_id", sa.BigInteger, unique=True, nullable=False),
        sa.Column("username", sa.String(100)),
        sa.Column("first_name", sa.String(100)),
        sa.Column("phone", sa.String(20)),
        sa.Column("display_name", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("is_blocked", sa.Boolean, server_default="false"),
    )
    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("client_id", sa.Integer, sa.ForeignKey("clients.id"), nullable=False),
        sa.Column("master_id", sa.Integer, sa.ForeignKey("masters.id"), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        sa.Column("total_price", sa.Numeric(10, 2)),
        sa.Column("total_duration_minutes", sa.Integer),
        sa.Column("status", sa.String(20), server_default="confirmed"),
        sa.Column("comment", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("reminder_24h_sent", sa.Boolean, server_default="false"),
        sa.Column("reminder_2h_sent", sa.Boolean, server_default="false"),
    )
    op.create_table(
        "booking_services",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("booking_id", sa.Integer, sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("service_id", sa.Integer, sa.ForeignKey("services.id"), nullable=False),
        sa.Column("price_at_booking", sa.Numeric(10, 2)),
        sa.Column("duration_at_booking", sa.Integer),
    )
    op.create_table(
        "gallery_photos",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("master_id", sa.Integer, sa.ForeignKey("masters.id"), nullable=False),
        sa.Column("file_id", sa.String(200), nullable=False),
        sa.Column("caption", sa.String(200)),
        sa.Column("sort_order", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("gallery_photos")
    op.drop_table("booking_services")
    op.drop_table("bookings")
    op.drop_table("clients")
    op.drop_table("schedule_exceptions")
    op.drop_table("schedule_templates")
    op.drop_table("services")
    op.drop_table("service_categories")
    op.drop_table("masters")
