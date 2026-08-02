# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A bot that polls target companies' ATS job boards and pings Discord when a new internship listing
appears. Runs on a GitHub Actions schedule (`.github/workflows/check-listings.yml`, every 15 min),
which commits the updated state file back to the repo after each run.

## Commands

```bash
pip install -r requirements.txt

# Preview matches without sending Discord notifications
python main.py --dry-run

# Send real notifications (requires DISCORD_WEBHOOK_URL)
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
python main.py
```

There is no test suite, linter, or build step configured. When adding a new adapter, verify it works
by hitting the real endpoint (`curl`, or `python main.py --dry-run`) rather than assuming shape from docs.

## Architecture

- `config.yaml` — the only thing most changes touch: `keywords`, `us_only`, and the `companies` list.
  Each company entry names an `ats` and `slug`, plus whatever extra fields that ATS needs.
- `adapters/` — one module per ATS, each exposing `fetch_jobs(slug, company_name, **extra) -> list[Job]`.
  Adapters are pure fetch/normalize: no keyword filtering, no state, no notification logic.
- `adapters/base.py` — the shared `Job` dataclass and `Adapter` protocol every adapter returns/implements.
- `adapters/us_location.py` — best-effort US-location detection, used when `us_only: true`. ATSes expose
  location/country differently: Ashby/Lever/Oracle/SmartRecruiters give a structured country field; others
  fall back to a heuristic over the location text (US state names/abbreviations, minus `NON_US_LOOKALIKES`
  like "Baja California" which contain a state name but aren't one). If country can't be determined at all,
  the job is kept rather than dropped — a missed real listing is worse than an occasional ambiguous one.
- `main.py` — orchestrates: loads config, calls each company's adapter, filters titles against `keywords`
  (via `matches_keywords`/`keyword_pattern`, which matches across `-`/space so "co-op" also matches "co op"),
  filters by location if `us_only`, diffs against `state/seen_jobs.json`, sends Discord notifications for
  anything new, and always persists `state/seen_jobs.json` in a `finally` block (so a mid-run crash doesn't
  replay every already-sent notification next run).
  - `ADAPTERS` maps `ats` name to the adapter's `fetch_jobs`.
  - `ADAPTER_EXTRA_ARGS` lists, per-ATS, which config keys beyond `slug`/`name` get passed through as kwargs.
  - `JOB_ENRICHERS` (currently Workday, TalentBrew) maps ATSes whose list endpoint doesn't expose country
    to a `fetch_details` function that looks it up per-job — only called for jobs that already passed the
    keyword filter, to limit extra requests.
  - Each company's adapter call and each job's enrichment/notification are wrapped individually so one
    broken adapter or one bad job doesn't take down the whole run.
- `notifiers/discord.py` — posts a Discord embed via webhook; retries on 429 with the API's `retry_after`
  rather than dropping the notification.
- `state/seen_jobs.json` — set of `"{company_name}:{job.id}"` keys already notified on; committed back to
  the repo by the workflow.

## Adding a company

Add an entry to `config.yaml` with `name`, `ats`, and `slug`. Supported ATS values and their quirks
(per-ATS required fields, slug format, endpoint gotchas) are documented in the README's "Adding a company"
section — read that before adding a new entry, especially for Workday, Oracle Fusion, Eightfold,
TalentBrew, and iCIMS, which need extra config fields or have non-obvious endpoint behavior.

If a company isn't on one of the existing ATSes, add a new adapter module implementing
`fetch_jobs(slug, company_name, **extra) -> list[Job]`, then register it in `main.py`'s `ADAPTERS`
(and `ADAPTER_EXTRA_ARGS` if it needs config fields beyond `slug`/`name`).
