from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum


class Section(str, Enum):
    FUNDING = "funding"
    SECTOR = "sector"
    TENDERS = "tenders"


@dataclass
class DigestItem:
    """Single story or link in the digest."""

    title: str
    url: str
    section: Section
    summary: str = ""
    source_name: str = ""
    published: datetime | None = None
    score: float = 0.0
    origin: str = "rss"  # rss | search | contracts
    relax_funding_strict: bool = False
    # OpenClaw-style routing (see categories.py)
    category: str = "network_other"
    deadline_at: date | None = None
    past_deadline: bool = False
    deadline_uncertain: bool = False
    event_past: bool = False

    def text_for_scoring(self) -> str:
        return f"{self.title} {self.summary}".lower()


@dataclass
class DigestBundle:
    """Grouped items ready for rendering."""

    funding: list[DigestItem] = field(default_factory=list)
    sector: list[DigestItem] = field(default_factory=list)
    tenders: list[DigestItem] = field(default_factory=list)

    def all_items(self) -> list[DigestItem]:
        return self.funding + self.sector + self.tenders
