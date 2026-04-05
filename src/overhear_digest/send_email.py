from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from overhear_digest.config import EnvSettings

logger = logging.getLogger(__name__)

RESEND_API = "https://api.resend.com/emails"
MAILJET_SEND_API = "https://api.mailjet.com/v3.1/send"

RFC_FROM_RE = re.compile(
    r"^(?P<name>.+?)\s*<(?P<email>[^>]+)>$",
)


def parse_from_header(value: str) -> tuple[str | None, str]:
    """Parse ``Name <email@domain.com>`` or plain email."""
    s = value.strip().strip('"').strip("'")
    m = RFC_FROM_RE.match(s)
    if m:
        return m.group("name").strip(), m.group("email").strip()
    return None, s


def effective_from_address(env: EnvSettings) -> str:
    return (env.email_from or env.resend_from or "").strip()


def send_via_resend(
    env: EnvSettings,
    subject: str,
    html: str,
    text: str,
    client: httpx.Client | None = None,
) -> None:
    if not env.resend_api_key:
        raise ValueError("RESEND_API_KEY is not set")
    if not env.digest_to_email:
        raise ValueError("DIGEST_TO_EMAIL is not set")
    from_addr = effective_from_address(env)
    if not from_addr:
        raise ValueError("Set EMAIL_FROM or RESEND_FROM to a verified sender address")

    payload = {
        "from": from_addr,
        "to": [e.strip() for e in env.digest_to_email.split(",") if e.strip()],
        "subject": subject,
        "html": html,
        "text": text,
    }

    headers = {
        "Authorization": f"Bearer {env.resend_api_key}",
        "Content-Type": "application/json",
    }

    own_client = client is None
    c = client or httpx.Client(timeout=30.0)
    try:
        r = c.post(RESEND_API, json=payload, headers=headers)
        if r.status_code >= 400:
            logger.error("Resend error %s: %s", r.status_code, r.text)
        r.raise_for_status()
        logger.info("Email sent (Resend): %s", r.json().get("id", "ok"))
    finally:
        if own_client:
            c.close()


def send_via_mailjet(
    env: EnvSettings,
    subject: str,
    html: str,
    text: str,
    client: httpx.Client | None = None,
) -> None:
    if not env.mailjet_api_key or not env.mailjet_secret_key:
        raise ValueError("MAILJET_API_KEY and MAILJET_SECRET_KEY must both be set")
    if not env.digest_to_email:
        raise ValueError("DIGEST_TO_EMAIL is not set")
    from_addr = effective_from_address(env)
    if not from_addr:
        raise ValueError("Set EMAIL_FROM (or RESEND_FROM) to a verified sender in Mailjet")

    name, email = parse_from_header(from_addr)
    from_obj: dict[str, str] = {"Email": email}
    if name:
        from_obj["Name"] = name

    to_list = []
    for raw in env.digest_to_email.split(","):
        e = raw.strip()
        if not e:
            continue
        tn, te = parse_from_header(e)
        entry: dict[str, str] = {"Email": te}
        if tn:
            entry["Name"] = tn
        to_list.append(entry)

    if not to_list:
        raise ValueError("DIGEST_TO_EMAIL has no valid addresses")

    payload = {
        "Messages": [
            {
                "From": from_obj,
                "To": to_list,
                "Subject": subject,
                "HTMLPart": html,
                "TextPart": text,
            }
        ]
    }

    own_client = client is None
    c = client or httpx.Client(
        timeout=30.0,
        auth=(env.mailjet_api_key, env.mailjet_secret_key),
    )
    try:
        r = c.post(
            MAILJET_SEND_API,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        if r.status_code >= 400:
            logger.error("Mailjet error %s: %s", r.status_code, r.text)
        r.raise_for_status()
        data = r.json()
        msgs = data.get("Messages") or []
        if msgs and isinstance(msgs[0], dict):
            first = msgs[0]
            st = first.get("Status")
            if st and st != "success":
                logger.error("Mailjet message status %s: %s", st, first)
                raise ValueError(f"Mailjet send failed: {first.get('Errors', first)}")
            to0 = (first.get("To") or [{}])[0]
            mid = to0.get("MessageUUID") or to0.get("MessageID")
            logger.info("Email sent (Mailjet): %s", mid or st or "ok")
        else:
            logger.info("Email sent (Mailjet)")
    finally:
        if own_client:
            c.close()


def send_digest_email(
    env: EnvSettings,
    subject: str,
    html: str,
    text: str,
    client: httpx.Client | None = None,
) -> None:
    """Use Mailjet when both keys are set; otherwise Resend if configured."""
    provider = (env.email_provider or "auto").lower().strip()
    if provider == "auto":
        if env.mailjet_api_key and env.mailjet_secret_key:
            send_via_mailjet(env, subject, html, text, client)
        elif env.resend_api_key:
            send_via_resend(env, subject, html, text, client)
        else:
            raise ValueError(
                "No email provider: set MAILJET_API_KEY + MAILJET_SECRET_KEY, "
                "or RESEND_API_KEY (and EMAIL_FROM / RESEND_FROM, DIGEST_TO_EMAIL)"
            )
    elif provider == "mailjet":
        send_via_mailjet(env, subject, html, text, client)
    elif provider == "resend":
        send_via_resend(env, subject, html, text, client)
    else:
        raise ValueError("EMAIL_PROVIDER must be auto, mailjet, or resend")
