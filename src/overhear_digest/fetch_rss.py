from __future__ import annotations

import logging
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING

import feedparser
import httpx

from overhear_digest.models import DigestItem, Section

if TYPE_CHECKING:
    from overhear_digest.config import RssFeedConfig

logger = logging.getLogger(__name__)

USER_AGENT = (
    "OVERHEAR-Digest/0.1 (+https://theoverhear.app; contact hello@theoverhear.app)"
)


def _parse_published(entry: feedparser.FeedParserDict) -> datetime | None:
    for key in ("published_parsed", "updated_parsed"):
        struct = getattr(entry, key, None)
        if struct:
            try:
                return datetime(*struct[:6])
            except (TypeError, ValueError):
                pass
    for key in ("published", "updated"):
        raw = getattr(entry, key, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except (TypeError, ValueError):
                pass
    return None


def _summary(entry: feedparser.FeedParserDict) -> str:
    if getattr(entry, "summary", None):
        s = entry.summary
        if len(s) > 500:
            return s[:497] + "..."
        return s
    return ""


def fetch_feed(client: httpx.Client, feed_cfg: RssFeedConfig) -> list[DigestItem]:
    section = Section(feed_cfg.section)
    source = feed_cfg.name or feed_cfg.url
    items: list[DigestItem] = []
    try:
        response = client.get(feed_cfg.url, follow_redirects=True, timeout=30.0)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.warning("RSS fetch failed %s: %s", feed_cfg.url, e)
        return items

    parsed = feedparser.parse(response.text)
    if parsed.bozo and not parsed.entries:
        logger.warning("RSS parse error %s: %s", feed_cfg.url, parsed.bozo_exception)
        return items

    for entry in parsed.entries:
        link = entry.get("link") or ""
        if not link:
            continue
        if feed_cfg.url_substrings_any and not any(
            s in link for s in feed_cfg.url_substrings_any
        ):
            continue
        title = entry.get("title", "(no title)").strip()
        items.append(
            DigestItem(
                title=title,
                url=link,
                section=section,
                summary=_summary(entry),
                source_name=source,
                published=_parse_published(entry),
                origin="rss",
                relax_funding_strict=feed_cfg.relax_funding_strict,
                category=feed_cfg.output_category,
            )
        )
    return items


def fetch_all_rss(
    client: httpx.Client, feed_configs: list[RssFeedConfig]
) -> list[DigestItem]:
    out: list[DigestItem] = []
    for fc in feed_configs:
        out.extend(fetch_feed(client, fc))
    return out
