import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

from adapters import ashby, eightfold, greenhouse, lever, oracle_fusion, smartrecruiters, workday
from adapters.base import Job
from notifiers import discord

ROOT = Path(__file__).parent
STATE_PATH = ROOT / "state" / "seen_jobs.json"

ADAPTERS = {
    "greenhouse": greenhouse.fetch_jobs,
    "ashby": ashby.fetch_jobs,
    "lever": lever.fetch_jobs,
    "workday": workday.fetch_jobs,
    "oracle_fusion": oracle_fusion.fetch_jobs,
    "smartrecruiters": smartrecruiters.fetch_jobs,
    "eightfold": eightfold.fetch_jobs,
}
# Config keys, beyond slug/name, that each adapter's fetch_jobs accepts as kwargs
ADAPTER_EXTRA_ARGS = {
    "workday": ["tenant", "site"],
    "oracle_fusion": ["host", "site_number", "site_alias"],
    "eightfold": ["domain"],
}
# ATSes where the list endpoint doesn't expose country, so it must be looked up per-job.
# Only called for jobs that already passed the keyword filter, to limit extra requests.
COUNTRY_ENRICHERS = {
    "workday": workday.fetch_country,
}


def load_config() -> dict:
    with open(ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def load_seen() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    with open(STATE_PATH) as f:
        return set(json.load(f))


def save_seen(seen: set[str]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump(sorted(seen), f, indent=2)
        f.write("\n")


def matches_keywords(title: str, keywords: list[str]) -> bool:
    return any(re.search(rf"\b{re.escape(keyword)}\b", title, re.IGNORECASE) for keyword in keywords)


def passes_location_filter(job: Job, company: dict, us_only: bool) -> Job:
    """Returns the (possibly country-enriched) job if it should be kept, else None-ish via job.country check by caller."""
    if not us_only or job.country is not None:
        return job

    enrich = COUNTRY_ENRICHERS.get(company["ats"])
    if enrich is None:
        return job  # no way to check further; default to keeping (don't hide possible matches)

    extra_args = {key: company[key] for key in ADAPTER_EXTRA_ARGS.get(company["ats"], [])}
    country = enrich(job, company["slug"], **extra_args)
    return Job(**{**job.__dict__, "country": country})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print matches instead of sending Discord notifications")
    args = parser.parse_args()

    config = load_config()
    keywords = config.get("keywords", [])
    us_only = config.get("us_only", False)
    seen = load_seen()
    new_seen = set(seen)

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not args.dry_run and not webhook_url:
        print("DISCORD_WEBHOOK_URL is not set", file=sys.stderr)
        return 1

    total_new = 0
    for company in config.get("companies", []):
        fetch_jobs = ADAPTERS[company["ats"]]
        extra_args = {key: company[key] for key in ADAPTER_EXTRA_ARGS.get(company["ats"], [])}
        jobs: list[Job] = fetch_jobs(company["slug"], company["name"], **extra_args)

        for job in jobs:
            if not matches_keywords(job.title, keywords):
                continue

            key = f"{company['name']}:{job.id}"
            if key in seen:
                continue

            job = passes_location_filter(job, company, us_only)
            new_seen.add(key)  # mark seen now so we don't re-check a known-excluded job every run

            if us_only and job.country is not None and job.country != "US":
                continue

            total_new += 1
            if args.dry_run:
                print(f"[NEW] {job.company} - {job.title} ({job.location}) [{job.country or 'unknown'}] {job.url}")
            else:
                discord.send(webhook_url, job)

    save_seen(new_seen)
    print(f"Done. {total_new} new internship listing(s) found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
