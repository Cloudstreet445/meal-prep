"""Server-side input sanitization for user-supplied content.

Defense-in-depth for anything a user can store and that later gets rendered
(pantry items, and — when added — user-created recipes). The frontend already
escapes with `_esc` on render, but we must not *rely* on that: a second client,
the Android app, an export, or a future template could render a field without
escaping. So we also neutralise dangerous content at the point of storage.

Two concerns:
  1. Stored XSS / "stored code" — strip HTML tags and control characters so a
     value like ``<img src=x onerror=alert(1)>`` or ``<script>…</script>`` can
     never be persisted as live markup. We keep the visible text, drop the tags.
  2. NoSQL operator injection into stored documents — reject dict keys that
     start with ``$`` or contain ``.`` so a raw dict can never smuggle a query
     operator (``$where``, ``$ne``, …) or a dotted path into a document.
"""

import re

# Matches any HTML/XML tag, e.g. <script>, </b>, <img ...>, <!-- -->
_TAG_RE = re.compile(r"<[^>]*>")
# Control chars except tab/newline/carriage-return
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Hard cap on any single free-text field to bound storage / DoS via huge payloads.
_MAX_FIELD_LEN = 2000


def clean_text(value, *, max_len: int = _MAX_FIELD_LEN) -> str:
    """Sanitize a single free-text string for safe storage.

    Strips HTML tags and control characters, collapses whitespace, and trims to
    ``max_len``. Returns a plain string (``None``/non-str coerced to "").
    """
    if value is None:
        return ""
    text = str(value)
    text = _TAG_RE.sub("", text)        # drop HTML tags (kills stored markup/JS)
    text = _CTRL_RE.sub("", text)       # drop control characters
    text = text.replace(" ", " ").replace(" ", " ")  # JS line separators
    text = re.sub(r"[ \t]+", " ", text).strip()
    return text[:max_len]


def reject_operator_keys(value):
    """Recursively reject Mongo operator/dotted keys in a dict or list.

    Returns the value unchanged if safe; raises ValueError if any key begins
    with ``$`` or contains ``.`` (which could alter query/update semantics if
    the structure were ever spread into a filter or ``$set`` document).
    """
    if isinstance(value, dict):
        for key, sub in value.items():
            if not isinstance(key, str) or key.startswith("$") or "." in key:
                raise ValueError(f"Illegal field name: {key!r}")
            reject_operator_keys(sub)
    elif isinstance(value, list):
        for item in value:
            reject_operator_keys(item)
    return value
