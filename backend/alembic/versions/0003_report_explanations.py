"""Add JSON columns for per-result explanations and doctor questions.

Revision ID: 0003_report_explanations
Revises: 0002_reports_raw_text
Create Date: 2026-08-22 21:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_report_explanations"
down_revision: Union[str, None] = "0002_reports_raw_text"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "reports",
        sa.Column(
            "result_explanations",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "reports",
        sa.Column(
            "doctor_questions",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("reports", "doctor_questions")
    op.drop_column("reports", "result_explanations")
