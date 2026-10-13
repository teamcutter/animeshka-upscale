"""users, sessions, jobs.user_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_sessions_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name="pk_sessions"),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # Existing jobs keep user_id = NULL: they were uploaded before accounts existed and are
    # not shown to anyone. On SQLite batch mode rebuilds `jobs` (env.py turns foreign keys off
    # for that), on PostgreSQL it is a plain ALTER TABLE.
    with op.batch_alter_table("jobs") as batch:
        batch.add_column(sa.Column("user_id", sa.Uuid(), nullable=True))
        batch.create_foreign_key(
            "fk_jobs_user_id_users", "users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_index("ix_jobs_user_id_created_at", ["user_id", "created_at"])


def downgrade() -> None:
    with op.batch_alter_table("jobs") as batch:
        batch.drop_index("ix_jobs_user_id_created_at")
        batch.drop_constraint("fk_jobs_user_id_users", type_="foreignkey")
        batch.drop_column("user_id")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_table("sessions")
    op.drop_table("users")
