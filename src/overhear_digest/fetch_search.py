from __future__ import annotations

import logging
import httpx

from overhear_digest.config import EnvSettings, SearchConfig, SearchQueryEntry
from overhear_digest.models import DigestItem, Section

logger = logging.getLogger(__name__)


def _search_brave(
    client: httpx.Client,
    api_key: str,
    query: str,
    count: int,
    *,
    freshness: str | None = None,
) -> list[tuple[str, str, str]]:
    """Return list of (title, url, description)."""
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "X-Subscription-Token": api_key,
    }
    params: dict[str, str | int] = {"q": query, "count": min(count, 20)}
    if freshness:
        params["freshness"] = freshness
    r = client.get(url, headers=headers, params=params, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("web", {}).get("results", []) or []:
        title = item.get("title") or ""
        u = item.get("url") or ""
        desc = item.get("description") or ""
        if title and u:
            results.append((title, u, desc))
    return results


def _search_tavily(
    client: httpx.Client,
    api_key: str,
    query: str,
    max_results: int,
) -> list[tuple[str, str, str]]:
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": min(max_results, 20),
        "search_depth": "basic",
    }
    r = client.post(url, json=payload, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("results", []) or []:
        title = item.get("title") or ""
        u = item.get("url") or ""
        content = item.get("content") or ""
        if title and u:
            results.append((title, u, content[:500]))
    return results


def _search_google_cse(
    client: httpx.Client,
    api_key: str,
    cx: str,
    query: str,
    num: int,
) -> list[tuple[str, str, str]]:
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": cx,
        "q": query,
        "num": min(num, 10),
    }
    r = client.get(url, params=params, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    results = []
    for item in data.get("items", []) or []:
        title = item.get("title") or ""
        u = item.get("link") or ""
        snippet = item.get("snippet") or ""
        if title and u:
            results.append((title, u, snippet))
    return results


def fetch_search_results(
    client: httpx.Client,
    search_cfg: SearchConfig,
    env: EnvSettings,
) -> list[DigestItem]:
    if not search_cfg.enabled or search_cfg.provider == "none":
        return []

    if search_cfg.provider == "brave" and not env.brave_api_key:
        logger.warning("Search disabled: BRAVE_API_KEY not set")
        return []
    if search_cfg.provider == "tavily" and not env.tavily_api_key:
        logger.warning("Search disabled: TAVILY_API_KEY not set")
        return []
    if search_cfg.provider == "google_cse" and (
        not env.google_api_key or not env.google_cse_id
    ):
        logger.warning(
            "Search disabled: GOOGLE_API_KEY or GOOGLE_CSE_ID not set",
        )
        return []

    query_entries: list[SearchQueryEntry] = search_cfg.queries[
        : search_cfg.max_queries_per_run
    ]
    if not query_entries:
        return []

    items: list[DigestItem] = []

    for qe in query_entries:
        count = qe.max_results or search_cfg.max_results_per_query
        q = qe.query
        try:
            if search_cfg.provider == "brave":
                fr = (qe.brave_freshness or "").strip() or (
                    search_cfg.brave_freshness or ""
                ).strip() or None
                rows = _search_brave(
                    client,
                    env.brave_api_key,
                    q,
                    count,
                    freshness=fr,
                )
            elif search_cfg.provider == "tavily":
                rows = _search_tavily(client, env.tavily_api_key, q, count)
            elif search_cfg.provider == "google_cse":
                rows = _search_google_cse(
                    client,
                    env.google_api_key,
                    env.google_cse_id,
                    q,
                    count,
                )
            else:
                return items
        except httpx.HTTPError as e:
            logger.warning("Search failed for %r: %s", q, e)
            continue

        for title, url, desc in rows:
            items.append(
                DigestItem(
                    title=title,
                    url=url,
                    section=Section.SECTOR,
                    summary=desc,
                    source_name=f"Search: {q[:55]}",
                    origin="search",
                    category=qe.category,
                )
            )

    return items
