from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from overhear_digest import categories as cat
from overhear_digest.config import DigestSettings
from overhear_digest.models import DigestItem
from overhear_digest.relevance import domain_host
from overhear_digest.textutil import strip_html


def drop_blocked_hosts(items: list[DigestItem], settings: DigestSettings) -> list[DigestItem]:
    blocked = {h.lower().lstrip(".") for h in settings.filters.blocked_hosts}
    out: list[DigestItem] = []
    for item in items:
        host = domain_host(item.url)
        if any(host == b or host.endswith("." + b) for b in blocked):
            continue
        out.append(item)
    return out


def drop_blocked_url_substrings(
    items: list[DigestItem], settings: DigestSettings
) -> list[DigestItem]:
    subs = [s.lower() for s in settings.filters.blocked_url_substrings]
    out: list[DigestItem] = []
    for item in items:
        u = item.url.lower()
        if any(s in u for s in subs):
            continue
        out.append(item)
    return out


def filter_by_recency(
    items: list[DigestItem],
    today: date,
    settings: DigestSettings,
) -> list[DigestItem]:
    """
    Drop items older than the configured calendar-year window.

    Uses ``published`` when present (RSS, contracts). For search hits without a
    date, infers a year from URL path segments and from 20xx mentions in the
    title or summary (ignoring years before today.year - 6 to reduce noise).
    """
    lim = settings.limits
    if not lim.recency_enabled:
        return items
    min_year = today.year - lim.recency_year_offset
    out: list[DigestItem] = []
    for item in items:
        if _item_passes_recency(item, today, min_year):
            out.append(item)
    return out


def _published_calendar_year(item: DigestItem) -> int | None:
    if item.published is None:
        return None
    pd = item.published
    if isinstance(pd, datetime):
        return pd.year
    return getattr(pd, "year", None)


def _years_in_url_path(url: str) -> list[int]:
    years: list[int] = []
    for seg in urlparse(url).path.split("/"):
        if len(seg) == 4 and seg.isdigit():
            y = int(seg)
            if 1998 <= y <= 2038:
                years.append(y)
    return years


def _recent_window_years_in_text(text: str, today: date) -> list[int]:
    lo = today.year - 6
    hi = today.year + 1
    found: list[int] = []
    for m in re.finditer(r"\b(20\d{2})\b", text):
        y = int(m.group(1))
        if lo <= y <= hi:
            found.append(y)
    return found


def _max_inferred_year_search(item: DigestItem, today: date) -> int | None:
    path_y = _years_in_url_path(item.url)
    blob = f"{item.title} {strip_html(item.summary, limit=500)}"
    text_y = _recent_window_years_in_text(blob, today)
    parts: list[int] = []
    if path_y:
        parts.append(max(path_y))
    if text_y:
        parts.append(max(text_y))
    if not parts:
        return None
    return max(parts)


def _item_passes_recency(item: DigestItem, today: date, min_year: int) -> bool:
    pub_y = _published_calendar_year(item)
    if pub_y is not None:
        return pub_y >= min_year

    if item.origin == "search":
        inferred = _max_inferred_year_search(item, today)
        if inferred is not None and inferred < min_year:
            return False
    return True


def filter_artscouncil_generic_pages(
    items: list[DigestItem], settings: DigestSettings
) -> list[DigestItem]:
    """Drop evergreen ACE hub pages; keep time-bound announcements on artscouncil.org.uk."""
    fc = settings.filters
    title_pats = [re.compile(p, re.I) for p in fc.ace_drop_title_patterns]
    url_subs = [s.lower() for s in fc.ace_drop_url_substrings]
    out: list[DigestItem] = []
    for item in items:
        u = item.url.lower()
        if "artscouncil.org.uk" not in u:
            out.append(item)
            continue
        blob = f"{item.title} {strip_html(item.summary, limit=500)}"
        if any(p.search(blob) for p in title_pats):
            continue
        if any(s in u for s in url_subs):
            continue
        out.append(item)
    return out


def filter_nlhf_rss_soft_news(
    items: list[DigestItem], settings: DigestSettings
) -> list[DigestItem]:
    """Drop NLHF blog posts that are awards, tips, or marketing — not actionable news."""
    pats = [re.compile(p, re.I) for p in settings.filters.nlhf_drop_patterns]
    out: list[DigestItem] = []
    for item in items:
        if item.origin != "rss" or "heritagefund.org.uk" not in item.url.lower():
            out.append(item)
            continue
        blob = f"{item.title} {item.summary}"
        if any(p.search(blob) for p in pats):
            continue
        out.append(item)
    return out


def filter_birmingham_scene_noise(
    items: list[DigestItem], settings: DigestSettings
) -> list[DigestItem]:
    """Remove Companies House, ticket aggregators, theatre-confusion hits, and empty snippets."""
    fc = settings.filters
    title_pats = [
        re.compile(p, re.I | re.DOTALL) for p in fc.birmingham_drop_title_patterns
    ]
    url_subs = [s.lower() for s in fc.birmingham_drop_url_substrings]
    min_c = fc.birmingham_min_summary_chars
    out: list[DigestItem] = []
    for item in items:
        if item.category != cat.BIRMINGHAM_BLACK_COUNTRY:
            out.append(item)
            continue
        u = item.url.lower()
        if any(s in u for s in url_subs):
            continue
        if any(p.search(item.title) for p in title_pats):
            continue
        if item.origin == "search":
            slen = len(strip_html(item.summary, limit=2000))
            if slen < min_c:
                continue
        out.append(item)
    return out


def _item_published_as_date(item: DigestItem) -> date | None:
    if item.published is None:
        return None
    p = item.published
    if isinstance(p, datetime):
        if p.tzinfo is not None:
            return p.astimezone(timezone.utc).date()
        return p.date()
    if isinstance(p, date):
        return p
    return None


def filter_birmingham_recency(
    items: list[DigestItem],
    today: date,
    settings: DigestSettings,
) -> list[DigestItem]:
    """
    Keep Birmingham & Black Country items within ~the last month: dated items by
    ``published``, search hits by title/URL year (drop prior calendar years) and
    rely on per-query Brave ``pm`` for index recency.
    """
    days = settings.filters.birmingham_max_age_days
    if days <= 0:
        return items
    out: list[DigestItem] = []
    cutoff = today - timedelta(days=days)
    for item in items:
        if item.category != cat.BIRMINGHAM_BLACK_COUNTRY:
            out.append(item)
            continue

        pub_d = _item_published_as_date(item)
        if pub_d is not None:
            if pub_d < cutoff:
                continue
            out.append(item)
            continue

        if item.origin == "search":
            title_years = _recent_window_years_in_text(item.title, today)
            if title_years and max(title_years) < today.year:
                continue
            path_y = _years_in_url_path(item.url)
            if path_y and max(path_y) < today.year:
                continue

        out.append(item)
    return out


def apply_funding_rss_gate(
    items: list[DigestItem], settings: DigestSettings
) -> list[DigestItem]:
    from overhear_digest.models import Section
    from overhear_digest.relevance import passes_funding_strict

    rel = settings.relevance
    out: list[DigestItem] = []
    for item in items:
        if (
            item.section == Section.FUNDING
            and not item.relax_funding_strict
            and not passes_funding_strict(
                item.text_for_scoring(),
                rel.funding_strict,
            )
        ):
            continue
        out.append(item)
    return out
