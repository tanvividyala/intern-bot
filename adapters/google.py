import datetime
import json
import re

import requests

from adapters.base import Job

RESULTS_URL = "https://www.google.com/about/careers/applications/jobs/results/"
# The results page has no JSON API; job data ships embedded in an AF_initDataCallback
# blob (Google's client-side hydration format) under the 'ds:1' key.
DS1_RE = re.compile(r"AF_initDataCallback\(\{key: 'ds:1'.*?data:(\[.*?\]), sideChannel", re.DOTALL)
# Like Amazon/Apple, careers.google.com is a single global site with full-text search
# rather than a per-company board. "internship" and "co-op" cover the same ground as a
# bare "intern" query (verified: every "intern" hit also turns up under one of these) with
# far fewer total pages to walk, so we search those and let main.py's title regex do the
# final filtering.
QUERIES = ["internship", "co-op"]


def _parse_jobs(html: str) -> list[list]:
    match = DS1_RE.search(html)
    if not match:
        return []
    return json.loads(match.group(1))[0] or []


def _job_location(locations: list) -> str:
    if not locations:
        return "Unknown"
    location = locations[0][0]
    if len(locations) > 1:
        location += f" (+{len(locations) - 1} more)"
    return location


def _job_country(locations: list) -> str | None:
    codes = [loc[5] for loc in locations if len(loc) > 5 and loc[5]]
    if not codes:
        return None
    return "US" if "US" in codes else codes[0]


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    """slug is unused: careers.google.com is Google's single global career site, not a
    multi-tenant ATS, so there's no per-company board to key off of."""
    by_id: dict[str, Job] = {}

    for query in QUERIES:
        page = 1
        while True:
            resp = requests.get(RESULTS_URL, params={"q": query, "page": page}, timeout=30)
            resp.raise_for_status()
            entries = _parse_jobs(resp.text)
            if not entries:
                break

            for entry in entries:
                job_id = entry[0]
                if job_id in by_id:
                    continue
                locations = entry[9] or []
                posted_ts = entry[12][0] if entry[12] else None
                by_id[job_id] = Job(
                    id=job_id,
                    title=entry[1],
                    company=company_name,
                    location=_job_location(locations),
                    url=f"https://www.google.com/about/careers/applications/jobs/results/{job_id}",
                    posted_at=datetime.datetime.fromtimestamp(posted_ts, datetime.timezone.utc).isoformat()
                    if posted_ts
                    else None,
                    country=_job_country(locations),
                )

            page += 1

    return list(by_id.values())
