"""Add raw_text column to reports for OCR output.

Revision ID: 0002_reports_raw_text
Revises: 0001_initial_schema
Create Date: 2026-08-22 20:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_reports_raw_text"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("raw_text", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("reports", "raw_text")
