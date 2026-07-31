import re

_TAG_RE = re.compile(r"<[^>]+>")
_SLUG_RE = re.compile(r"[^a-z0-9]+")

WORDS_PER_MINUTE = 200


def reading_time_minutes(html: str) -> int:
    text = _TAG_RE.sub(" ", html)
    word_count = len(text.split())
    return max(1, round(word_count / WORDS_PER_MINUTE))


def slugify(title: str) -> str:
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "post"
