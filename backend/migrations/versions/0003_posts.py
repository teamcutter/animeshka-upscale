"""posts: jobs shared in the public feed

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "posts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["job_id"], ["jobs.id"], name="fk_posts_job_id_jobs", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_posts"),
        sa.UniqueConstraint("job_id", name="uq_posts_job_id"),
    )
    op.create_index("ix_posts_published_at_id", "posts", ["published_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_posts_published_at_id", table_name="posts")
    op.drop_table("posts")
