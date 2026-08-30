"""Add value_text and allow nullable numeric value for qualitative findings.

Revision ID: 0004_test_result_value_text
Revises: 0003_report_explanations
Create Date: 2026-08-23 02:10:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_test_result_value_text"
down_revision: Union[str, None] = "0003_report_explanations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "test_results",
        sa.Column("value_text", sa.String(length=128), nullable=True),
    )
    op.alter_column(
        "test_results",
        "value",
        existing_type=sa.Float(),
        nullable=True,
    )


def downgrade() -> None:
    op.execute("UPDATE test_results SET value = 0 WHERE value IS NULL")
    op.alter_column(
        "test_results",
        "value",
        existing_type=sa.Float(),
        nullable=False,
    )
    op.drop_column("test_results", "value_text")
