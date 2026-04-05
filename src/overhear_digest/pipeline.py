from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx

from overhear_digest.compile_openclaw import OpenClawView, compile_openclaw_view
from overhear_digest.config import load_digest_settings, load_env
from overhear_digest.deadlines import apply_deadline_classification, item_should_drop_entirely
from overhear_digest.fetch_contracts import fetch_contracts_finder
from overhear_digest.fetch_rss import USER_AGENT, fetch_all_rss
from overhear_digest.fetch_search import fetch_search_results
from overhear_digest.filters import (
    apply_funding_rss_gate,
    drop_blocked_hosts,
    drop_blocked_url_substrings,
    filter_artscouncil_generic_pages,
    filter_birmingham_scene_noise,
    filter_by_recency,
    filter_nlhf_rss_soft_news,
)
from overhear_digest.history import apply_history_to_items
from overhear_digest.score import apply_scores, dedupe_items


def build_openclaw_digest(
    config_path: Path | None,
    today: date,
    *,
    ignore_history: bool,
) -> tuple[OpenClawView, object, object, dict[str, str] | None, int, int]:
    """
    Returns (view, settings, env, hist_pruned_or_none, hist_skipped, raw_count_after_dedupe).
    """
    settings = load_digest_settings(config_path)
    env = load_env()

    with httpx.Client(
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=30.0,
    ) as client:
        rss_items = fetch_all_rss(client, settings.rss_feeds)
        contract_items = fetch_contracts_finder(
            client,
            settings.contracts_finder,
            settings,
        )
        search_items = fetch_search_results(client, settings.search, env)

    items = dedupe_items(rss_items + contract_items + search_items)
    raw_n = len(items)
    items = drop_blocked_hosts(items, settings)
    items = drop_blocked_url_substrings(items, settings)
    items = filter_artscouncil_generic_pages(items, settings)
    items = filter_nlhf_rss_soft_news(items, settings)
    items = apply_funding_rss_gate(items, settings)
    apply_scores(items, settings)
    min_s = settings.limits.min_score_search
    items = [
        i
        for i in items
        if not (i.origin == "search" and i.score < min_s)
    ]
    items = filter_birmingham_scene_noise(items, settings)
    items = filter_by_recency(items, today, settings)
    for i in items:
        apply_deadline_classification(i, today)
    items = [i for i in items if not item_should_drop_entirely(i)]

    items, hist_pruned, _, hist_skipped = apply_history_to_items(
        items,
        settings,
        env,
        today,
        ignore=ignore_history,
    )

    view = compile_openclaw_view(items, settings, today)
    return view, settings, env, hist_pruned, hist_skipped, raw_n
