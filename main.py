import argparse
import json
import os
import re
import sys
from pathlib import Path

import yaml

from adapters import ashby, greenhouse, workday
from adapters.base import Job
from notifiers import discord

ROOT = Path(__file__).parent
STATE_PATH = ROOT / "state" / "seen_jobs.json"

ADAPTERS = {
    "greenhouse": greenhouse.fetch_jobs,
    "ashby": ashby.fetch_jobs,
    "workday": workday.fetch_jobs,
}
# Config keys, beyond slug/name, that each adapter's fetch_jobs accepts as kwargs
ADAPTER_EXTRA_ARGS = {
    "workday": ["tenant", "site"],
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print matches instead of sending Discord notifications")
    args = parser.parse_args()

    config = load_config()
    keywords = config.get("keywords", [])
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

            total_new += 1
            new_seen.add(key)
            if args.dry_run:
                print(f"[NEW] {job.company} - {job.title} ({job.location}) {job.url}")
            else:
                discord.send(webhook_url, job)

    save_seen(new_seen)
    print(f"Done. {total_new} new internship listing(s) found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
