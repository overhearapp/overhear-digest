from __future__ import annotations

import re

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
