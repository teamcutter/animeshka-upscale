import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from src.features.upscale.domain import Job, MediaKind, Mode, now_utc

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_MICROSECOND = timedelta(microseconds=1)

COMMENT_MAX_LENGTH = 1000
DESCRIPTION_MAX_LENGTH = 2000
TAG_MAX_LENGTH = 50
MAX_TAGS_PER_POST = 30

# A hashtag is '#' followed by letters (any alphabet), digits or '_': #аниме, #4k, #studio_ghibli.
# Not preceded by a word character, so "a#b" or "C#" in the middle of a word is not a tag.
_HASHTAG = re.compile(rf"(?<!\w)#(\w{{1,{TAG_MAX_LENGTH}}})(?!\w)")
_TAG = re.compile(rf"^\w{{1,{TAG_MAX_LENGTH}}}$")


def normalize_tag(value: str) -> str:
    """A tag as stored and searched: no leading '#', lower case.

    Raises ValueError if it isn't a valid tag (letters, digits, '_', up to 50 chars).
    """
    tag = value.strip().removeprefix("#").lower()
    if not _TAG.match(tag):
        raise ValueError(f"Invalid tag: {value!r}")
    return tag


def extract_tags(description: str | None) -> list[str]:
    """Hashtags of a description, lower-cased, without repeats, in order of appearance."""
    if not description:
        return []
    tags = dict.fromkeys(match.lower() for match in _HASHTAG.findall(description))
    return list(tags)[:MAX_TAGS_PER_POST]


# Search sees a description as words: "#studio_ghibli" gives "studio_ghibli", "studio", "ghibli".
_WORD = re.compile(r"\w+")
_WORD_PART = re.compile(r"[^\W_]+")
SEARCH_QUERY_MAX_LENGTH = 200
SEARCH_MAX_TERMS = 10


def extract_words(description: str | None) -> list[str]:
    """Lower-case words of a description (hashtags included, without '#') for the search index."""
    if not description:
        return []
    text = description.lower()
    words = dict.fromkeys(
        word[:TAG_MAX_LENGTH] for word in (*_WORD.findall(text), *_WORD_PART.findall(text))
    )
    return list(words)


@dataclass(frozen=True)
class SearchQuery:
    """A parsed search: "арбуз #помидор -огурец" -> terms [арбуз, помидор], excluded [огурец].

    Each term matches a word starting with it ("арбуз" finds "арбузы", "#арбузный").
    """

    terms: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()

    @classmethod
    def parse(cls, text: str) -> "SearchQuery":
        """Raises ValueError for too many terms."""
        terms: dict[str, None] = {}
        excluded: dict[str, None] = {}
        for token in text.lower().split():
            target = excluded if token.startswith("-") else terms
            for word in _WORD.findall(token):
                target[word[:TAG_MAX_LENGTH]] = None
        for word in excluded:
            terms.pop(word, None)
        if len(terms) > SEARCH_MAX_TERMS or len(excluded) > SEARCH_MAX_TERMS:
            raise ValueError(f"Too many words in the query (max {SEARCH_MAX_TERMS})")
        return cls(terms=tuple(terms), excluded=tuple(excluded))


@dataclass(frozen=True)
class SearchFilters:
    query: SearchQuery = field(default_factory=SearchQuery)
    kind: MediaKind | None = None
    mode: Mode | None = None
    # Display name of the author, case-insensitive.
    author: str | None = None


@dataclass
class Post:
    """A finished job its owner shared in the public feed."""

    job_id: UUID
    id: UUID = field(default_factory=uuid4)
    published_at: datetime = field(default_factory=now_utc)
    # Free text written by the author; its #hashtags make the post findable by tag.
    description: str | None = None

    @property
    def tags(self) -> list[str]:
        return extract_tags(self.description)


@dataclass
class TagCount:
    tag: str
    posts: int


@dataclass
class FeedItem:
    post: Post
    job: Job
    # Only the display name: the feed never shows the author's email.
    author_name: str
    like_count: int = 0
    comment_count: int = 0
    # Whether the user reading the feed liked this post.
    liked: bool = False
    # Search only: how many of the query's words the post has (results are ordered by it).
    relevance: int = 0


@dataclass
class Comment:
    post_id: UUID
    author_id: UUID
    text: str
    id: UUID = field(default_factory=uuid4)
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class CommentView:
    comment: Comment
    author_name: str
    # The owner of the commented post: they may delete any comment under it.
    post_owner_id: UUID | None


@dataclass(frozen=True)
class Cursor:
    """Where the next page starts: rows strictly past (at, id) in the listing order.

    Paging by (timestamp, id) instead of offset keeps pages stable while new rows arrive.
    The feed uses it for posts (published_at), comments for their created_at.
    """

    at: datetime
    id: UUID

    def encode(self) -> str:
        micros = (self.at - _EPOCH) // _MICROSECOND
        return f"{micros}.{self.id.hex}"

    @classmethod
    def decode(cls, value: str) -> "Cursor":
        """Raises ValueError if the cursor was not made by encode()."""
        micros, _, row_id = value.partition(".")
        try:
            at = _EPOCH + int(micros) * _MICROSECOND
        except OverflowError as exc:  # a number far outside the datetime range
            raise ValueError(f"Cursor date out of range: {micros}") from exc
        return cls(at=at, id=UUID(hex=row_id))


@dataclass
class FeedPage:
    items: list[FeedItem]
    next_cursor: Cursor | None


@dataclass
class CommentPage:
    items: list[CommentView]
    next_cursor: Cursor | None


@dataclass(frozen=True)
class SearchCursor:
    """Next search page: posts after this one in (relevance desc, published_at desc, id desc)."""

    relevance: int
    position: Cursor

    def encode(self) -> str:
        return f"{self.relevance}:{self.position.encode()}"

    @classmethod
    def decode(cls, value: str) -> "SearchCursor":
        """Raises ValueError if the cursor was not made by encode()."""
        relevance, sep, position = value.partition(":")
        if not sep or not relevance.isdigit():
            raise ValueError(f"Invalid search cursor: {value}")
        return cls(relevance=int(relevance), position=Cursor.decode(position))


@dataclass
class SearchPage:
    items: list[FeedItem]
    next_cursor: SearchCursor | None
    query: SearchQuery
