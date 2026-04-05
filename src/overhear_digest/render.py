from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from overhear_digest.config import DigestSettings
from overhear_digest.models import DigestBundle


def _template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "templates"


def _format_digest_date(d: date) -> str:
    try:
        return d.strftime("%A %-d %B %Y")
    except ValueError:
        return d.strftime(f"%A {d.day} %B %Y")


def render_digest(
    bundle: DigestBundle,
    settings: DigestSettings,
    run_date: date | None = None,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body)."""
    run_date = run_date or date.today()
    env = Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=select_autoescape(["html", "xml"]),
    )
    ctx = {
        "date": _format_digest_date(run_date),
        "date_iso": run_date.isoformat(),
        "funding": bundle.funding,
        "sector": bundle.sector,
        "tenders": bundle.tenders,
        "item_count": len(bundle.all_items()),
    }

    subject = settings.email.subject_template.format(date=ctx["date"])
    html_t = env.get_template("digest.html.j2")
    text_t = env.get_template("digest.txt.j2")
    return subject, html_t.render(**ctx), text_t.render(**ctx)
