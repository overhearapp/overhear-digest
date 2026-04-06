from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from overhear_digest.config import DigestSettings, KeywordRule
from overhear_digest.models import DigestBundle, DigestItem, Section
from overhear_digest.relevance import domain_host, passes_funding_strict


def published_sort_key(published: datetime | None) -> float:
    """Stable ordering for mixed naive/aware datetimes (avoids TypeError in sort)."""
    if published is None:
        return float("-inf")
    if published.tzinfo is not None:
        return published.timestamp()
    return published.replace(tzinfo=timezone.utc).timestamp()


def normalize_url(url: str) -> str:
    """Strip tracking params and trivial differences for deduplication."""
    parsed = urlparse(url.strip())
    query_pairs = parse_qs(parsed.query, keep_blank_values=False)
    filtered = {
        k: v
        for k, v in query_pairs.items()
        if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}
    }
    new_query = urlencode(filtered, doseq=True)
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/") or "/"
    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            netloc,
            path,
            "",
            new_query,
            "",
        )
    )


def keyword_score(text: str, keywords: list[KeywordRule]) -> float:
    t = text.lower()
    total = 0.0
    for rule in keywords:
        if rule.term.lower() in t:
            total += rule.weight
    return total


def apply_scores(items: list[DigestItem], settings: DigestSettings) -> None:
    limits = settings.limits
    for item in items:
        kw = keyword_score(item.text_for_scoring(), settings.keywords)
        if item.origin == "rss":
            item.score = limits.rss_base_score + kw
        elif item.origin == "contracts":
            item.score = limits.contracts_base_score + kw
        else:
            item.score = kw


def dedupe_items(items: list[DigestItem]) -> list[DigestItem]:
    seen: set[str] = set()
    unique: list[DigestItem] = []
    for item in items:
        key = normalize_url(item.url)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def filter_and_bucket(items: list[DigestItem], settings: DigestSettings) -> DigestBundle:
    limits = settings.limits
    bundle = DigestBundle()
    rel = settings.relevance

    # Split by section, drop weak search hits
    by_section: dict[Section, list[DigestItem]] = {
        Section.FUNDING: [],
        Section.SECTOR: [],
        Section.TENDERS: [],
    }
    for item in items:
        if item.origin == "search" and item.score < limits.min_score_search:
            continue
        if (
            item.section == Section.FUNDING
            and not item.relax_funding_strict
            and not passes_funding_strict(
                item.text_for_scoring(),
                rel.funding_strict,
            )
        ):
            continue
        by_section[item.section].append(item)

    def sort_and_trim(section: Section) -> list[DigestItem]:
        lst = by_section[section]
        lst.sort(
            key=lambda x: (x.score, published_sort_key(x.published)),
            reverse=True,
        )
        if section == Section.SECTOR and rel.dedupe_one_per_domain_sector:
            lst = _dedupe_one_per_domain(lst)
        return lst[: limits.max_items_per_section]

    bundle.funding = sort_and_trim(Section.FUNDING)
    bundle.sector = sort_and_trim(Section.SECTOR)
    bundle.tenders = sort_and_trim(Section.TENDERS)
    return bundle


def _dedupe_one_per_domain(items: list[DigestItem]) -> list[DigestItem]:
    seen_hosts: set[str] = set()
    out: list[DigestItem] = []
    for item in items:
        h = domain_host(item.url)
        if not h or h in seen_hosts:
            continue
        seen_hosts.add(h)
        out.append(item)
    return out
