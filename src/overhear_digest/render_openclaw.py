from __future__ import annotations

from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from overhear_digest import categories as cat
from overhear_digest.compile_openclaw import OpenClawView, display_summary
from overhear_digest.config import DigestSettings


def _template_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "templates"


def _format_digest_date(d: date) -> str:
    try:
        return d.strftime("%A %-d %B %Y")
    except ValueError:
        return d.strftime(f"%A {d.day} %B %Y")


def render_openclaw_digest(
    view: OpenClawView,
    settings: DigestSettings,
    run_date: date | None = None,
) -> tuple[str, str, str]:
    run_date = run_date or date.today()
    env = Environment(
        loader=FileSystemLoader(str(_template_dir())),
        autoescape=select_autoescape(["html", "xml"]),
    )
    env.globals["display_summary"] = display_summary
    env.globals["why"] = cat.WHY_FOR_CATEGORY

    ctx = {
        "date": _format_digest_date(run_date),
        "date_iso": run_date.isoformat(),
        "view": view,
        "item_count": len(view.all_items_for_history()),
    }

    subject = settings.email.subject_template.format(date=ctx["date"])
    html_t = env.get_template("openclaw.html.j2")
    text_t = env.get_template("openclaw.txt.j2")
    return subject, html_t.render(**ctx), text_t.render(**ctx)
