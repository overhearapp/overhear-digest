from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class KeywordRule(BaseModel):
    term: str
    weight: float = 1.0


class RssFeedConfig(BaseModel):
    url: str
    section: Literal["funding", "sector", "tenders"]
    name: str = ""
    # If non-empty, only keep items whose link contains at least one substring
    url_substrings_any: list[str] = Field(default_factory=list)
    # Skip culture/health text gate for funding (use with url_substrings_any, not alone)
    relax_funding_strict: bool = False
    # OpenClaw digest section (see overhear_digest.categories)
    output_category: str = "network_other"


class SearchQueryEntry(BaseModel):
    query: str
    category: str = "network_other"
    max_results: int | None = None
    # Brave only; overrides search.brave_freshness for this query (e.g. pm = past month for local news)
    brave_freshness: str | None = None


class SearchConfig(BaseModel):
    enabled: bool = True
    provider: Literal["brave", "tavily", "google_cse", "none"] = "brave"
    max_results_per_query: int = 3
    max_queries_per_run: int = 25
    # Brave only: bias toward recent pages (py ≈ past year). See Brave Web Search API freshness param.
    brave_freshness: str | None = "py"
    queries: list[SearchQueryEntry] = Field(default_factory=list)

    @field_validator("queries", mode="before")
    @classmethod
    def _coerce_legacy_string_queries(cls, v: object) -> object:
        if not isinstance(v, list):
            return v
        out: list[object] = []
        for x in v:
            if isinstance(x, str):
                out.append({"query": x, "category": "network_other"})
            else:
                out.append(x)
        return out


class EmailConfig(BaseModel):
    subject_template: str = "OVERHEAR digest — {date}"


class BriefingCapsConfig(BaseModel):
    culture_central_max: int = 3
    chwa_max: int = 2


class FilterConfig(BaseModel):
    blocked_hosts: list[str] = Field(
        default_factory=lambda: [
            "wikipedia.org",
            "wikimedia.org",
            "wiktionary.org",
            "skiddle.com",
            "ents24.com",
            "federalregister.gov",
            "regulations.gov",
        ]
    )
    # Drop if URL contains any of these (Companies House, ticket hubs, etc.)
    blocked_url_substrings: list[str] = Field(
        default_factory=lambda: [
            "find-and-update.company-information.service.gov.uk",
            "skiddle.com",
            "ents24.com",
        ]
    )
    # NLHF RSS: remove award stories, listicles, marketing — keep sharper news you can act on
    nlhf_drop_patterns: list[str] = Field(
        default_factory=lambda: [
            r"grant acknowledgement",
            r"competition:\s*enter your creative",
            r"\b(six|seven|five|four|\d+)\s+tips\s+for\b",
            r"autism-friendly",
            r"we['’]ve awarded",
            r"we['’]ve invested",
            r"how our grant",
            r"turbocharged",
            r"benefit from long-term investment",
            r"heritage places, the next chapter",
            r"special offers and free entry",
            r"national lottery open week",
            r"how community grants can support",
            r"heritage leaders of tomorrow",
            r"future heritage leadership",
            r"kickstart your heritage career",
            r"get paid to learn about heritage sector governance",
            r"royal observatory greenwich",
            r"conserve and celebrate historic churches",
            r"royal air force and royal marines heritage",
        ]
    )
    # Birmingham & Black Country: title/snippet noise from search
    birmingham_drop_title_patterns: list[str] = Field(
        default_factory=lambda: [
            r"Find upcoming events at",
            r"Upcoming Events.*Tickets",
            r"\|\s*Birmingham Rep",
            r"Company information\s*-\s*GOV\.UK",
            r"overview\s*-\s*Find and update company information",
            r"^Sandra Hall,\s*Friction Arts",
            r"look back at (our|the)",
            r"\bA look back\b",
            r"\|\s*Flickr",
            r"\bFlickr\b",
        ]
    )
    birmingham_drop_url_substrings: list[str] = Field(
        default_factory=lambda: [
            "birmingham-rep.co.uk",
            "find-and-update.company-information.service.gov.uk",
            "flickr.com",
        ]
    )
    # Search hits with almost no snippet are usually directory junk
    birmingham_min_summary_chars: int = 48
    # Birmingham & Black Country: drop RSS/items older than this many days (0 = off)
    birmingham_max_age_days: int = 31
    # artscouncil.org.uk: drop evergreen “open funds / system update / NPLG hub” pages, not one-off announcements
    ace_drop_title_patterns: list[str] = Field(
        default_factory=lambda: [
            r"grants system update",
            r"^our open funds\b",
            r"\bour open funds\s*\|\s*arts council",
            r"national lottery project grants\s*\|\s*arts council",
            r"^arts council national lottery project grants\b",
            r"^looking for funding\?\s*have a look at our open funds",
            # Boilerplate in body when title is slightly different
            r"we['’]ve updated our grants system",
            r"rolling programme national lottery project grants anytime",
            r"manage regular funding and keep in touch with us on the system",
        ]
    )
    ace_drop_url_substrings: list[str] = Field(
        default_factory=lambda: [
            "artscouncil.org.uk/funding/our-open-funds",
            "artscouncil.org.uk/funding/apply-for-funding",
        ]
    )


class LimitsConfig(BaseModel):
    max_items_per_section: int = 12
    max_time_sensitive_items: int = 15
    max_worth_checking_items: int = 8
    min_score_search: float = 0.55
    rss_base_score: float = 2.0
    contracts_base_score: float = 1.2
    # Drop stale items: keep current and previous calendar year when dated (published or inferred).
    recency_enabled: bool = True
    # min allowed calendar year = today.year - this value (1 → allow this year and last year only)
    recency_year_offset: int = 1


class ContractsFinderConfig(BaseModel):
    """UK Contracts Finder OCDS JSON API (not RSS)."""

    enabled: bool = True
    published_from_days: int = 14
    fetch_size: int = 60
    require_keyword_match: bool = True
    # culture: any phrase matches; health_creative: culture OR (health AND bridge)
    match_mode: Literal["legacy_keywords", "health_creative"] = "health_creative"


class FundingRelevanceConfig(BaseModel):
    """Drop GOV.UK noise: keep culture/heritage/creative industries, or health+creative bridge."""

    enabled: bool = True
    culture_phrases: list[str] = Field(
        default_factory=lambda: [
            "arts council",
            "national lottery project",
            "project grants",
            "heritage",
            "museum",
            "libraries",
            "library service",
            "creative industries",
            "cultural sector",
            "cultural ",
            " arts ",
            "theatre",
            "theater",
            "literature",
            "poetry",
            "participatory",
            "community arts",
            "gallery",
            "archives",
            "archive",
            "crafts",
            " carnival",
            "film council",
            "dcms",
        ]
    )
    health_phrases: list[str] = Field(
        default_factory=lambda: [
            "nhs",
            "hospital",
            "health trust",
            "foundation trust",
            "clinical",
            "social care",
            "care quality",
            " cqc",
            "gp ",
            "patient",
            "ambulance",
            "mental health",
            "wellbeing hub",
        ]
    )
    creative_bridge_phrases: list[str] = Field(
        default_factory=lambda: [
            "arts",
            "art ",
            "wellbeing",
            "well-being",
            "creative",
            "culture",
            "heritage",
            "community",
            "engagement",
            "participat",
            "involve people",
            "charity",
            "voluntary",
            "psychosocial",
        ]
    )


class TendersRelevanceConfig(BaseModel):
    """Contracts Finder: culture-oriented OR health/social with a creative-community signal."""

    culture_phrases: list[str] = Field(
        default_factory=lambda: [
            "arts",
            "heritage",
            "museum",
            "library",
            "cultural ",
            "creative ",
            "community engagement",
            "participatory",
            "participation agreement",  # avoid matching “participate in the tender”
            "workshop",
            "festival",
            "poetry",
            "audio",
            "interpretation",
            "exhibition",
            "archives",
            "third sector",
            "voluntary sector",
            "artist",
            "storytelling",
            "engagement officer",
            "community outreach",
            "experts by experience",
            "evaluation of",  # programme evaluation, not “evaluation criteria”
        ]
    )
    health_phrases: list[str] = Field(
        default_factory=lambda: [
            "nhs",
            "hospital",
            "health trust",
            "foundation trust",
            "clinical",
            "social care",
            " cqc",
            "patient",
            "mental health",
        ]
    )
    health_creative_bridge_phrases: list[str] = Field(
        default_factory=lambda: [
            "arts",
            " art ",
            "wellbeing",
            "well-being",
            "creative",
            "culture",
            "heritage",
            "community",
            " engagement",
            "participatory",
            "charity",
            "voluntary sector",
            "psychosocial",
            "lived experience",
            "experts by experience",
            " engage ",
        ]
    )


class RelevanceConfig(BaseModel):
    funding_strict: FundingRelevanceConfig = Field(default_factory=FundingRelevanceConfig)
    tenders: TendersRelevanceConfig = Field(default_factory=TendersRelevanceConfig)
    dedupe_one_per_domain_sector: bool = True


class HistoryConfig(BaseModel):
    """Skip URLs that appeared in a sent digest within the last ``days`` days."""

    enabled: bool = True
    days: int = 7
    path: str = "data/digest_history.json"


class DigestSettings(BaseModel):
    rss_feeds: list[RssFeedConfig] = Field(default_factory=list)
    search: SearchConfig = Field(default_factory=SearchConfig)
    contracts_finder: ContractsFinderConfig = Field(default_factory=ContractsFinderConfig)
    relevance: RelevanceConfig = Field(default_factory=RelevanceConfig)
    history: HistoryConfig = Field(default_factory=HistoryConfig)
    filters: FilterConfig = Field(default_factory=FilterConfig)
    briefing_caps: BriefingCapsConfig = Field(default_factory=BriefingCapsConfig)
    keywords: list[KeywordRule] = Field(default_factory=list)
    email: EmailConfig = Field(default_factory=EmailConfig)
    limits: LimitsConfig = Field(default_factory=LimitsConfig)


class EnvSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Email: Mailjet (preferred when keys set) or Resend — see send_digest_email()
    mailjet_api_key: str = ""
    mailjet_secret_key: str = ""
    resend_api_key: str = ""
    # Verified sender, e.g. "OVERHEAR Digest <hello@yourdomain.com>"
    email_from: str = ""
    resend_from: str = ""
    digest_to_email: str = ""
    email_provider: str = "auto"
    brave_api_key: str = ""
    tavily_api_key: str = ""
    google_api_key: str = ""
    google_cse_id: str = ""
    digest_history_path: str = ""


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def resolve_history_path(settings: DigestSettings, env: EnvSettings) -> Path:
    raw = (env.digest_history_path or "").strip() or settings.history.path
    p = Path(raw)
    if p.is_absolute():
        return p
    return project_root() / p


def default_config_path() -> Path:
    env_path = os.environ.get("DIGEST_CONFIG")
    if env_path:
        return Path(env_path)
    return project_root() / "config" / "digest.yaml"


def load_digest_settings(path: Path | None = None) -> DigestSettings:
    cfg_path = path or default_config_path()
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return DigestSettings.model_validate(data)


def load_env() -> EnvSettings:
    return EnvSettings()
