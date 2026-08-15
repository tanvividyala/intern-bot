import argparse
import json
import os
import re
import sys
from pathlib import Path

import requests
import yaml

from adapters import amazon, apple, ashby, bamboohr, eightfold, google, greenhouse, icims, lever, oleeo, oracle_fusion, smartrecruiters, talentbrew, workday
from adapters.base import Job
from notifiers import discord

ROOT = Path(__file__).parent

ADAPTERS = {
    "greenhouse": greenhouse.fetch_jobs,
    "ashby": ashby.fetch_jobs,
    "lever": lever.fetch_jobs,
    "workday": workday.fetch_jobs,
    "oracle_fusion": oracle_fusion.fetch_jobs,
    "smartrecruiters": smartrecruiters.fetch_jobs,
    "eightfold": eightfold.fetch_jobs,
    "talentbrew": talentbrew.fetch_jobs,
    "icims": icims.fetch_jobs,
    "amazon": amazon.fetch_jobs,
    "apple": apple.fetch_jobs,
    "google": google.fetch_jobs,
    "bamboohr": bamboohr.fetch_jobs,
    "oleeo": oleeo.fetch_jobs,
}
# Config keys, beyond slug/name, that each adapter's fetch_jobs accepts as kwargs. Optional ones
# are simply left out of the company's config entry, falling back to the adapter's default.
ADAPTER_EXTRA_ARGS = {
    "workday": ["tenant", "site"],
    "oracle_fusion": ["host", "site_number", "site_alias"],
    "eightfold": ["domain", "host", "api"],
    "oleeo": ["vacancy_ids"],
}
# ATSes where the list endpoint doesn't expose country (and sometimes not an exact title either),
# so it's looked up per-job. Only called for jobs that already passed the keyword filter, to limit
# extra requests. Each returns the Job fields it resolved.
JOB_ENRICHERS = {
    "workday": workday.fetch_details,
    "talentbrew": talentbrew.fetch_details,
}


def default_state_path(config_path: Path) -> Path:
    """config.yaml -> state/seen_jobs.json; config.<board>.yaml -> state/seen_jobs.<board>.json."""
    stem = config_path.stem  # e.g. "config" or "config.vedh"
    suffix = stem[len("config"):]  # "" or ".vedh"
    return ROOT / "state" / f"seen_jobs{suffix}.json"


def load_config(config_path: Path) -> dict:
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_seen(state_path: Path) -> set[str]:
    if not state_path.exists():
        return set()
    with open(state_path) as f:
        return set(json.load(f))


def save_seen(seen: set[str], state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    with open(state_path, "w") as f:
        json.dump(sorted(seen), f, indent=2)
        f.write("\n")


def adapter_args(company: dict) -> dict:
    return {key: company[key] for key in ADAPTER_EXTRA_ARGS.get(company["ats"], []) if key in company}


def keyword_pattern(keyword: str) -> str:
    """Matches the keyword however its words are separated, so 'co-op' also matches 'co op' —
    titles derived from URL slugs (TalentBrew) lose the punctuation."""
    words = [re.escape(word) for word in re.split(r"[\s-]+", keyword.strip()) if word]
    return r"\b" + r"[\s-]+".join(words) + r"\b"


def matches_keywords(title: str, keywords: list[str]) -> bool:
    return any(re.search(keyword_pattern(keyword), title, re.IGNORECASE) for keyword in keywords)


def enrich_job(job: Job, company: dict, us_only: bool) -> Job:
    """Fills in fields the ATS's list endpoint didn't expose (notably country) from a per-job lookup."""
    if not us_only or job.country is not None:
        return job

    enrich = JOB_ENRICHERS.get(company["ats"])
    if enrich is None:
        return job  # no way to check further; default to keeping (don't hide possible matches)

    try:
        details = enrich(job, company["slug"], **adapter_args(company))
    except requests.RequestException as e:
        print(f"Skipping detail lookup for {company['name']} job {job.id}: {e}", file=sys.stderr)
        return job
    return Job(**{**job.__dict__, **details})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print matches instead of sending Discord notifications")
    parser.add_argument("--config", default="config.yaml", help="Path to the board's config file (default: config.yaml)")
    parser.add_argument("--state", default=None, help="Path to the board's seen-jobs state file (default: derived from --config)")
    parser.add_argument(
        "--webhook-env",
        default="DISCORD_WEBHOOK_URL",
        help="Env var to read the Discord webhook URL from (default: DISCORD_WEBHOOK_URL)",
    )
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = ROOT / config_path
    state_path = Path(args.state) if args.state else default_state_path(config_path)

    config = load_config(config_path)
    keywords = config.get("keywords", [])
    exclude_keywords = config.get("exclude_keywords", [])
    us_only = config.get("us_only", False)
    seen = load_seen(state_path)
    new_seen = set(seen)

    webhook_url = os.environ.get(args.webhook_env)
    if not args.dry_run and not webhook_url:
        print(f"{args.webhook_env} is not set", file=sys.stderr)
        return 1

    total_new = 0
    try:
        for company in config.get("companies", []):
            fetch_jobs = ADAPTERS[company["ats"]]
            try:
                jobs: list[Job] = fetch_jobs(company["slug"], company["name"], **adapter_args(company))
            except Exception as e:
                # Catches adapter bugs (bad API responses, etc.) too, not just network errors --
                # one company's broken adapter should never take down the whole run and, with it,
                # the state save below for every company already processed.
                print(f"Skipping {company['name']}: {e}", file=sys.stderr)
                continue

            for job in jobs:
                if not matches_keywords(job.title, keywords):
                    continue
                if matches_keywords(job.title, exclude_keywords):
                    continue

                key = f"{company['name']}:{job.id}"
                if key in seen:
                    continue

                try:
                    job = enrich_job(job, company, us_only)

                    if us_only and job.country is not None and job.country != "US":
                        new_seen.add(key)  # legitimate exclusion; don't re-check this job every run
                        continue

                    total_new += 1
                    if args.dry_run:
                        # Preview only -- don't mark seen, so a genuinely new match still gets a
                        # real notification once this is run for real.
                        print(f"[NEW] {job.company} - {job.title} ({job.location}) [{job.country or 'unknown'}] {job.url}")
                    else:
                        # Clearbit's free logo API (logo.clearbit.com) was shut down; Google's
                        # favicon service is a reliable, no-key-required replacement.
                        logo_url = f"https://www.google.com/s2/favicons?domain={company['domain']}&sz=128" if company.get("domain") else None
                        discord.send(webhook_url, job, logo_url)
                        # Only mark seen once the notification actually went out -- a failed send
                        # (bad webhook, exhausted retries) should be retried next run, not dropped.
                        new_seen.add(key)
                except Exception as e:
                    print(f"Skipping {company['name']} job {job.id}: {e}", file=sys.stderr)
    finally:
        # Always persist whatever was marked seen, even if something above raised unexpectedly --
        # otherwise a single crash mid-run replays every notification already sent this run on
        # the next invocation, since nothing else records that they went out.
        save_seen(new_seen, state_path)

    print(f"Done. {total_new} new internship listing(s) found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
