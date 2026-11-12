"""likes and comments on feed posts

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "likes",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], name="fk_likes_post_id_posts", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_likes_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("post_id", "user_id", name="pk_likes"),
    )
    op.create_index("ix_likes_user_id", "likes", ["user_id"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], name="fk_comments_post_id_posts", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name="fk_comments_user_id_users", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_comments"),
    )
    op.create_index(
        "ix_comments_post_id_created_at_id", "comments", ["post_id", "created_at", "id"]
    )
    op.create_index("ix_comments_user_id", "comments", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_comments_user_id", table_name="comments")
    op.drop_index("ix_comments_post_id_created_at_id", table_name="comments")
    op.drop_table("comments")
    op.drop_index("ix_likes_user_id", table_name="likes")
    op.drop_table("likes")
