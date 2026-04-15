import re
import unicodedata

_PUNCT_RE = re.compile(r"[^a-z0-9\s\-]")


def normalize(s: str) -> str:
    """Normalize a string by stripping accents, lowercasing, dropping punctuation, and collapsing whitespace.

    Args:
        s: Input string to normalize.

    Returns:
        Normalized string with accents removed, lowercased, punctuation removed (except hyphens),
        and whitespace collapsed to single spaces.
    """
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower()
    s = " ".join(s.split())
    s = _PUNCT_RE.sub(" ", s)
    s = " ".join(s.split())
    return s
