"""Initial schema: users, reports, test_results.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-22 19:40:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

result_status = postgresql.ENUM(
    "NORMAL",
    "HIGH",
    "LOW",
    name="result_status",
    create_type=False,
)


def upgrade() -> None:
    result_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "reports",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("file_url", sa.String(length=1024), nullable=False),
        sa.Column("report_type", sa.String(length=100), nullable=False),
        sa.Column("ai_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_reports_user_id"), "reports", ["user_id"], unique=False)

    op.create_table(
        "test_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("report_id", sa.UUID(), nullable=False),
        sa.Column("marker_name", sa.String(length=255), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("reference_min", sa.Float(), nullable=True),
        sa.Column("reference_max", sa.Float(), nullable=True),
        sa.Column("status", result_status, nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["reports.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_test_results_report_id"),
        "test_results",
        ["report_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_test_results_report_id"), table_name="test_results")
    op.drop_table("test_results")
    op.drop_index(op.f("ix_reports_user_id"), table_name="reports")
    op.drop_table("reports")
    op.drop_table("users")
    result_status.drop(op.get_bind(), checkfirst=True)
