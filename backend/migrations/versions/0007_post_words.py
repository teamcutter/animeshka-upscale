"""word index of post descriptions for full-text search

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-19
"""

import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of src.features.feed.domain.extract_words as of this revision: a migration
# must keep doing the same thing even if the app's tokenizer changes later.
_WORD = re.compile(r"\w+")
_WORD_PART = re.compile(r"[^\W_]+")


def _words(description: str) -> list[str]:
    text = description.lower()
    return list(dict.fromkeys(w[:50] for w in (*_WORD.findall(text), *_WORD_PART.findall(text))))


def upgrade() -> None:
    post_words = op.create_table(
        "post_words",
        sa.Column("post_id", sa.Uuid(), nullable=False),
        sa.Column("word", sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(
            ["post_id"], ["posts.id"], name="fk_post_words_post_id_posts", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("post_id", "word", name="pk_post_words"),
    )
    op.create_index("ix_post_words_word_post_id", "post_words", ["word", "post_id"])

    # Index the posts that already have a description (written since migration 0006).
    posts = sa.table("posts", sa.column("id", sa.Uuid()), sa.column("description", sa.Text()))
    rows = op.get_bind().execute(sa.select(posts).where(posts.c.description.is_not(None)))
    words = [
        {"post_id": post_id, "word": word}
        for post_id, description in rows
        for word in _words(description)
    ]
    if words:
        op.bulk_insert(post_words, words)


def downgrade() -> None:
    op.drop_index("ix_post_words_word_post_id", table_name="post_words")
    op.drop_table("post_words")
