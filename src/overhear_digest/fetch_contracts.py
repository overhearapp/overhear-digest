from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

import httpx

from overhear_digest import categories as cat
from overhear_digest.config import ContractsFinderConfig, DigestSettings
from overhear_digest.models import DigestItem, Section
from overhear_digest.relevance import passes_tenders_match

logger = logging.getLogger(__name__)


def _notice_url(release: dict[str, Any]) -> str:
    tender = release.get("tender") or {}
    for doc in tender.get("documents") or []:
        u = doc.get("url") or ""
        if "contractsfinder.service.gov.uk/Notice/" in u:
            return u
    rid = release.get("id") or ""
    # id is often "{uuid}-{suffix}"
    m = re.match(r"^([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", rid)
    if m:
        return f"https://www.contractsfinder.service.gov.uk/Notice/{m.group(1)}"
    return ""


def fetch_contracts_finder(
    client: httpx.Client,
    cf_cfg: ContractsFinderConfig,
    settings: DigestSettings,
) -> list[DigestItem]:
    if not cf_cfg.enabled:
        return []

    start = date.today() - timedelta(days=cf_cfg.published_from_days)
    size = min(max(cf_cfg.fetch_size, 1), 100)
    url = (
        "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
        f"?publishedFrom={start.isoformat()}&size={size}"
    )

    try:
        r = client.get(url, timeout=45.0)
        r.raise_for_status()
        data = r.json()
    except (httpx.HTTPError, ValueError) as e:
        logger.warning("Contracts Finder fetch failed: %s", e)
        return []

    releases = data.get("releases") or []
    items: list[DigestItem] = []

    for release in releases:
        tender = release.get("tender") or {}
        title = (tender.get("title") or "").strip()
        if not title:
            continue
        desc = (tender.get("description") or "").strip()
        blob = f"{title} {desc}"
        if cf_cfg.require_keyword_match and not passes_tenders_match(
            blob,
            cf_cfg.match_mode,
            settings.relevance.tenders,
            settings.keywords,
        ):
            continue
        link = _notice_url(release)
        if not link:
            continue
        pub_raw = tender.get("datePublished") or release.get("date")
        published = None
        if pub_raw:
            try:
                published = datetime.fromisoformat(str(pub_raw).replace("Z", "+00:00"))
            except ValueError:
                pass

        summary = desc[:500] + ("..." if len(desc) > 500 else "") if desc else ""
        items.append(
            DigestItem(
                title=title,
                url=link,
                section=Section.TENDERS,
                summary=summary,
                source_name="Contracts Finder",
                published=published,
                origin="contracts",
                category=cat.FUNDING_OPPORTUNITIES,
            )
        )

    return items
