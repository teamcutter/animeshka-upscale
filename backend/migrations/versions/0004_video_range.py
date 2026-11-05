"""Persist selected video intervals.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "jobs", sa.Column("start_seconds", sa.Float(), nullable=False, server_default="0")
    )
    op.add_column("jobs", sa.Column("end_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "end_seconds")
    op.drop_column("jobs", "start_seconds")
