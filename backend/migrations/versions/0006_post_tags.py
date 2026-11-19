"""post descriptions and hashtag index

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable: posts published before this migration simply have no description.
    with op.batch_alter_table("posts") as batch:
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))

    op.create_table(
        "post_tags",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("tag", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], name="fk_post_tags_post_id_posts", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("post_id", "tag", name="pk_post_tags"),
    )
    op.create_index("ix_post_tags_tag_post_id", "post_tags", ["tag", "post_id"])


def downgrade() -> None:
    op.drop_index("ix_post_tags_tag_post_id", table_name="post_tags")
    op.drop_table("post_tags")
    with op.batch_alter_table("posts") as batch:
        batch.drop_column("description")
