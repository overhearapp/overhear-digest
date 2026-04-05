from __future__ import annotations

import html as html_module
import re


def strip_html(raw: str, limit: int = 400) -> str:
    """Remove HTML tags, decode entities, collapse whitespace for summaries."""
    if not raw:
        return ""
    s = html_module.unescape(raw)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if len(s) > limit:
        return s[: limit - 1] + "…"
    return s
