from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime

from overhear_digest import categories as cat
from overhear_digest.config import DigestSettings
from overhear_digest.models import DigestItem
from overhear_digest.score import normalize_url, published_sort_key
from overhear_digest.textutil import strip_html


@dataclass
class OpenClawView:
    culture_central: list[DigestItem] = field(default_factory=list)
    chwa: list[DigestItem] = field(default_factory=list)
    time_sensitive: list[DigestItem] = field(default_factory=list)
    funding: list[DigestItem] = field(default_factory=list)
    birmingham: list[DigestItem] = field(default_factory=list)
    audio: list[DigestItem] = field(default_factory=list)
    poetry: list[DigestItem] = field(default_factory=list)
    arts_health: list[DigestItem] = field(default_factory=list)
    network: list[DigestItem] = field(default_factory=list)
    worth_checking: list[DigestItem] = field(default_factory=list)

    def all_items_for_history(self) -> list[DigestItem]:
        seen: set[str] = set()
        out: list[DigestItem] = []
        for lst in (
            self.culture_central,
            self.chwa,
            self.time_sensitive,
            self.funding,
            self.birmingham,
            self.audio,
            self.poetry,
            self.arts_health,
            self.network,
            self.worth_checking,
        ):
            for item in lst:
                k = normalize_url(item.url)
                if k in seen:
                    continue
                seen.add(k)
                out.append(item)
        return out


def _dedupe_domain(items: list[DigestItem]) -> list[DigestItem]:
    from overhear_digest.relevance import domain_host

    seen: set[str] = set()
    out: list[DigestItem] = []
    for item in items:
        h = domain_host(item.url)
        if h in seen:
            continue
        seen.add(h)
        out.append(item)
    return out


def _sort_by_deadline(items: list[DigestItem]) -> list[DigestItem]:
    return sorted(
        items,
        key=lambda x: (
            x.deadline_at or date.max,
            x.score,
            published_sort_key(x.published),
        ),
    )


def _sort_default(items: list[DigestItem]) -> list[DigestItem]:
    return sorted(
        items,
        key=lambda x: (x.score, published_sort_key(x.published)),
        reverse=True,
    )


def compile_openclaw_view(
    items: list[DigestItem],
    settings: DigestSettings,
    today: date,
) -> OpenClawView:
    """
    Build section lists. Items with a confirmed future deadline are placed only
    in time_sensitive (soonest first). Worth checking = deadline language but
    unparseable date.
    """
    lim = settings.limits
    caps = settings.briefing_caps

    ts_keys: set[str] = set()
    time_sensitive: list[DigestItem] = []
    for item in items:
        if item.deadline_at and item.deadline_at >= today:
            time_sensitive.append(item)
            ts_keys.add(normalize_url(item.url))
    time_sensitive = _sort_by_deadline(time_sensitive)

    worth: list[DigestItem] = []
    grouped: dict[str, list[DigestItem]] = {k: [] for k in (
        cat.BRIEFING_CULTURE_CENTRAL,
        cat.BRIEFING_CHWA,
        cat.FUNDING_OPPORTUNITIES,
        cat.BIRMINGHAM_BLACK_COUNTRY,
        cat.AUDIO_WALKING_ARTS,
        cat.POETRY_PLACE,
        cat.ARTS_HEALTH,
        cat.NETWORK_OTHER,
    )}
    for item in items:
        if normalize_url(item.url) in ts_keys:
            continue
        if item.deadline_uncertain:
            worth.append(item)
            continue
        c = item.category
        if c in grouped:
            grouped[c].append(item)
        else:
            grouped[cat.NETWORK_OTHER].append(item)

    birmingham = grouped[cat.BIRMINGHAM_BLACK_COUNTRY]
    if settings.relevance.dedupe_one_per_domain_sector:
        birmingham = _dedupe_domain(birmingham)

    view = OpenClawView(
        culture_central=_sort_default(grouped[cat.BRIEFING_CULTURE_CENTRAL])[
            : caps.culture_central_max
        ],
        chwa=_sort_default(grouped[cat.BRIEFING_CHWA])[: caps.chwa_max],
        time_sensitive=time_sensitive[: lim.max_time_sensitive_items],
        funding=_sort_default(grouped[cat.FUNDING_OPPORTUNITIES])[
            : lim.max_items_per_section
        ],
        birmingham=_sort_default(birmingham)[: lim.max_items_per_section],
        audio=_sort_default(grouped[cat.AUDIO_WALKING_ARTS])[
            : lim.max_items_per_section
        ],
        poetry=_sort_default(grouped[cat.POETRY_PLACE])[: lim.max_items_per_section],
        arts_health=_sort_default(grouped[cat.ARTS_HEALTH])[
            : lim.max_items_per_section
        ],
        network=_sort_default(grouped[cat.NETWORK_OTHER])[
            : lim.max_items_per_section
        ],
        worth_checking=_sort_default(worth)[: lim.max_worth_checking_items],
    )
    return view


def display_summary(item: DigestItem) -> str:
    return strip_html(item.summary, limit=220) or strip_html(item.title, limit=120)
