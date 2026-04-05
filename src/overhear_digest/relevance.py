from __future__ import annotations

from urllib.parse import urlparse

from overhear_digest.config import (
    FundingRelevanceConfig,
    KeywordRule,
    TendersRelevanceConfig,
)


def domain_host(url: str) -> str:
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        return host[4:]
    return host


def passes_funding_strict(text: str, cfg: FundingRelevanceConfig) -> bool:
    if not cfg.enabled:
        return True
    t = f" {text.lower()} "
    if any(p.lower() in t for p in cfg.culture_phrases):
        return True
    health_hit = any(p.lower() in t for p in cfg.health_phrases)
    bridge_hit = any(p.lower() in t for p in cfg.creative_bridge_phrases)
    return bool(health_hit and bridge_hit)


def passes_tenders_match(
    text: str,
    mode: str,
    tenders_cfg: TendersRelevanceConfig,
    keywords: list[KeywordRule],
) -> bool:
    t = f" {text.lower()} "
    if mode == "legacy_keywords":
        return any(rule.term.lower() in t for rule in keywords)

    culture = any(p.lower() in t for p in tenders_cfg.culture_phrases)
    health = any(p.lower() in t for p in tenders_cfg.health_phrases)
    bridge = any(p.lower() in t for p in tenders_cfg.health_creative_bridge_phrases)
    return culture or (health and bridge)
