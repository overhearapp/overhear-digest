# OVERHEAR digest

Daily email digest for [OVERHEAR](https://theoverhear.app): aggregates **RSS/Atom feeds**, **UK Contracts Finder** (OCDS JSON), and optional **web search** (Brave, Tavily, or Google Programmable Search), then scores items against configurable keywords and sends one HTML email via **Mailjet** or **Resend**.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
cp .env.example .env        # fill in secrets
overhear-digest --dry-run --print-email
overhear-digest             # send email
```

## Configuration

- **[config/digest.yaml](config/digest.yaml)** — RSS sources, `contracts_finder` (OCDS), search provider and queries, keywords, section limits, **`history`** (default 7 days: omit URLs already emailed recently; see `data/digest_history.json`).
- **Environment variables** (see [.env.example](.env.example)):
  - **Email:** `DIGEST_TO_EMAIL`, and a verified sender in `EMAIL_FROM` (or legacy `RESEND_FROM`).
  - **Mailjet (recommended if you already use it):** `MAILJET_API_KEY` and `MAILJET_SECRET_KEY` from your Mailjet account. With both set, they are used automatically unless `EMAIL_PROVIDER=resend`.
  - **Resend (alternative):** `RESEND_API_KEY` only; used when Mailjet keys are not set, or when `EMAIL_PROVIDER=resend`.
  - **One search key** (optional but recommended): `BRAVE_API_KEY`, or `TAVILY_API_KEY`, or `GOOGLE_API_KEY` + `GOOGLE_CSE_ID`.
  - `EMAIL_PROVIDER` — `auto` (default), `mailjet`, or `resend`.
  - `DIGEST_CONFIG` — optional path to an alternate YAML config.
  - `DIGEST_HISTORY_PATH` — optional override for the URL history file (defaults to `history.path` in YAML).

Use **`overhear-digest --ignore-history`** to bypass filtering and writes (useful when debugging). **`--dry-run`** still applies history filtering so the preview matches what would be sent, but does not update the file.

### Search providers

Set `search.provider` in `digest.yaml` to `brave`, `tavily`, `google_cse`, or `none`. Match the corresponding env vars.

### Contracts Finder

Public JSON endpoint; notices are filtered with `require_keyword_match` against your keyword list so the tenders section stays relevant. Tune **keywords** and **`published_from_days` / `fetch_size`** as needed.

### RSS sources

Some sites block datacentre IPs or bots. If a feed fails in GitHub Actions but works locally, try replacing it with a **Google Alerts** feed (delivered as RSS) or another mirror. Arts Council England’s site is often difficult to fetch automatically; use gov.uk search atoms and Brave/Tavily queries instead.

## GitHub Actions

Workflow: [.github/workflows/daily-digest.yml](.github/workflows/daily-digest.yml). A **cache** step persists `data/digest_history.json` between runs so the 7-day deduplication applies in CI as well as locally.

Add these **repository secrets**:

| Secret | Required |
|--------|----------|
| `DIGEST_TO_EMAIL` | Yes (comma-separated allowed) |
| `EMAIL_FROM` | Yes — verified sender, e.g. `OVERHEAR Digest <you@domain.com>` |
| `MAILJET_API_KEY` / `MAILJET_SECRET_KEY` | Yes for Mailjet (default when both are set) |
| `RESEND_API_KEY` | Only if using Resend instead of Mailjet |
| `RESEND_FROM` | Optional legacy alias for `EMAIL_FROM` |
| `EMAIL_PROVIDER` | Optional: `auto`, `mailjet`, or `resend` |
| `BRAVE_API_KEY` | If `search.provider` is `brave` |
| `TAVILY_API_KEY` | If `search.provider` is `tavily` |
| `GOOGLE_API_KEY` / `GOOGLE_CSE_ID` | If `search.provider` is `google_cse` |

Run manually via **Actions → Daily OVERHEAR digest → Run workflow**.

## Project layout

```
config/digest.yaml       # Feeds, queries, keywords
src/overhear_digest/     # Fetch, score, render, send
templates/               # Jinja2 email templates
```

## Licence

Use and modify for OVERHEAR Ltd’s internal operations; add a licence file if you open-source the repo.
