"""Create reports table

Revision ID: 001
Revises: None
Create Date: 2026-01-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), unique=True, nullable=False, index=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "completed", "failed", name="reportstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("age", sa.Integer, nullable=True),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("ocr_text", sa.Text, nullable=True),
        sa.Column("result_json", sa.Text, nullable=True),
        sa.Column("result_markdown", sa.Text, nullable=True),
        sa.Column("result_pdf_path", sa.String(500), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "source",
            sa.Enum("web", "whatsapp", name="reportsource"),
            nullable=False,
            server_default="web",
        ),
        sa.Column("whatsapp_number", sa.String(20), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("reports")
