from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Iterable

from overhear_digest.config import DigestSettings, EnvSettings, resolve_history_path
from overhear_digest.models import DigestItem
from overhear_digest.score import normalize_url

logger = logging.getLogger(__name__)


def _parse_iso(d: str) -> date | None:
    try:
        return date.fromisoformat(d.strip()[:10])
    except ValueError:
        return None


def load_url_dates(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read digest history %s: %s", path, e)
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str) and _parse_iso(v):
            out[k] = v[:10]
    return out


def urls_to_skip(
    url_dates: dict[str, str],
    today: date,
    days: int,
) -> tuple[dict[str, str], set[str]]:
    if days <= 0:
        return url_dates, set()

    pruned: dict[str, str] = {}
    skip: set[str] = set()
    for url_norm, seen_s in url_dates.items():
        seen = _parse_iso(seen_s)
        if seen is None:
            continue
        age = (today - seen).days
        if age < days:
            pruned[url_norm] = seen_s[:10]
            skip.add(url_norm)
    return pruned, skip


def filter_items_by_history(
    items: list[DigestItem],
    skip_urls: set[str],
) -> tuple[list[DigestItem], int]:
    kept: list[DigestItem] = []
    n = 0
    for item in items:
        key = normalize_url(item.url)
        if key in skip_urls:
            n += 1
            continue
        kept.append(item)
    return kept, n


def record_sent_urls(
    pruned_base: dict[str, str],
    items: Iterable[DigestItem],
    today: date,
    days: int,
) -> dict[str, str]:
    merged = dict(pruned_base)
    for item in items:
        merged[normalize_url(item.url)] = today.isoformat()
    if days <= 0:
        return merged
    return {
        u: d
        for u, d in merged.items()
        if (seen := _parse_iso(d)) is not None and (today - seen).days < days
    }


def save_url_dates(path: Path, url_dates: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(dict(sorted(url_dates.items())), indent=2) + "\n",
        encoding="utf-8",
    )


def apply_history_to_items(
    items: list[DigestItem],
    settings: DigestSettings,
    env: EnvSettings,
    today: date,
    *,
    ignore: bool,
) -> tuple[list[DigestItem], dict[str, str] | None, set[str], int]:
    if ignore or not settings.history.enabled:
        return items, None, set(), 0

    path = resolve_history_path(settings, env)
    raw = load_url_dates(path)
    pruned, skip = urls_to_skip(raw, today, settings.history.days)
    filtered, skipped = filter_items_by_history(items, skip)
    return filtered, pruned, skip, skipped


def persist_history_after_send_items(
    settings: DigestSettings,
    env: EnvSettings,
    pruned_before_send: dict[str, str],
    sent_items: list[DigestItem],
    today: date,
) -> None:
    path = resolve_history_path(settings, env)
    final = record_sent_urls(pruned_before_send, sent_items, today, settings.history.days)
    save_url_dates(path, final)
    logger.info("Recorded %s URLs in digest history", len(sent_items))
