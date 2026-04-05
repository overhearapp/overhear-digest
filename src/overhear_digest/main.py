from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import httpx

from overhear_digest.config import default_config_path
from overhear_digest.history import persist_history_after_send_items
from overhear_digest.pipeline import build_openclaw_digest
from overhear_digest.render_openclaw import render_openclaw_digest
from overhear_digest.send_email import send_digest_email

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(message)s",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build and send the OVERHEAR digest")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and score but print summary only (no email)",
    )
    parser.add_argument(
        "--print-email",
        action="store_true",
        help="With --dry-run, also print text body to stdout",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="Path to digest.yaml (default: config/digest.yaml or DIGEST_CONFIG)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose logging (includes HTTP client)",
    )
    parser.add_argument(
        "--ignore-history",
        action="store_true",
        help="Do not filter or update 7-day URL history (debugging)",
    )
    args = parser.parse_args(argv)

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger("httpx").setLevel(logging.INFO)

    cfg = args.config or default_config_path()
    if not cfg.is_file():
        logger.error("Config not found: %s", cfg)
        return 1

    today = date.today()
    view, settings, env, hist_pruned, hist_skipped, raw_n = build_openclaw_digest(
        cfg,
        today,
        ignore_history=args.ignore_history,
    )
    subject, html_body, text_body = render_openclaw_digest(view, settings, today)

    n = len(view.all_items_for_history())
    logger.info(
        "Digest: %s items in send (after filters; %s URLs before history)",
        n,
        raw_n,
    )
    if hist_skipped:
        logger.info("Skipped %s URLs already sent within history window", hist_skipped)

    if args.dry_run:
        if args.print_email:
            print(text_body)
        return 0

    try:
        send_digest_email(env, subject, html_body, text_body)
    except ValueError as e:
        logger.error("%s", e)
        return 1
    except httpx.HTTPError as e:
        logger.error("Email send failed: %s", e)
        return 1

    if (
        hist_pruned is not None
        and settings.history.enabled
        and not args.ignore_history
    ):
        persist_history_after_send_items(
            settings,
            env,
            hist_pruned,
            view.all_items_for_history(),
            today,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
