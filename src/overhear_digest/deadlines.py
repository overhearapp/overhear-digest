from __future__ import annotations

import re
from datetime import date

from overhear_digest.models import DigestItem
from overhear_digest.textutil import strip_html

DEADLINE_HINT = re.compile(
    r"\b(deadline|closes?|closing date|close on|apply by|applications?\s+(close|due)|"
    r"submission(?:s)?\s+by|must\s+(apply|submit)|last\s+chance|"
    r"expressions?\s+of\s+interest|eoi)\b",
    re.I,
)

EVENT_HINT = re.compile(
    r"\b(event|launch|opening|private view|pv|workshop on|seminar on|"
    r"conference|festival)\b",
    re.I,
)

_MONTHS = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

_RE_D_MON_Y = re.compile(
    r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
    r"(January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[,\s]+(20\d{2})\b",
    re.I,
)
_RE_ISO = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
_RE_DMY = re.compile(r"\b(\d{1,2})/(\d{1,2})/(20\d{2})\b")


def _parse_dates_from_text(text: str) -> list[date]:
    found: list[date] = []
    for m in _RE_D_MON_Y.finditer(text):
        d, mon, y = m.groups()
        mi = _MONTHS.get(mon.lower()[:3]) or _MONTHS.get(mon.lower())
        if mi:
            try:
                found.append(date(int(y), mi, int(d)))
            except ValueError:
                pass
    for m in _RE_ISO.finditer(text):
        y, mo, d = m.groups()
        try:
            found.append(date(int(y), int(mo), int(d)))
        except ValueError:
            pass
    for m in _RE_DMY.finditer(text):
        a, b, y = m.groups()
        da, db = int(a), int(b)
        yi = int(y)
        # Prefer DMY when first token > 12
        if da > 12:
            try:
                found.append(date(yi, db, da))
            except ValueError:
                pass
        elif db > 12:
            try:
                found.append(date(yi, da, db))
            except ValueError:
                pass
        else:
            try:
                found.append(date(yi, db, da))
            except ValueError:
                try:
                    found.append(date(yi, da, db))
                except ValueError:
                    pass
    return found


def apply_deadline_classification(item: DigestItem, today: date) -> None:
    """Set deadline_at, past_deadline, deadline_uncertain, event_past on item."""
    text = strip_html(f"{item.title} {item.summary}", limit=2000)

    dates = _parse_dates_from_text(text)
    has_deadline_lang = bool(DEADLINE_HINT.search(text))
    has_event_lang = bool(EVENT_HINT.search(text))

    if dates:
        future = [d for d in dates if d >= today]
        past = [d for d in dates if d < today]
        if has_deadline_lang:
            if future:
                item.deadline_at = min(future)
            elif past:
                item.past_deadline = True
            else:
                item.deadline_uncertain = True
        if has_event_lang and past and not future:
            item.event_past = True
    elif has_deadline_lang:
        item.deadline_uncertain = True


def item_should_drop_entirely(item: DigestItem) -> bool:
    """Drop items with confirmed past deadline or past-only event language."""
    if item.past_deadline:
        return True
    if getattr(item, "event_past", False):
        return True
    return False
