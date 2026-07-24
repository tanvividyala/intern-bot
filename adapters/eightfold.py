import requests

from adapters.base import Job
from adapters.us_location import detect_country

PAGE_SIZE = 10


def fetch_jobs(slug: str, company_name: str, domain: str) -> list[Job]:
    """slug is the Eightfold tenant subdomain (e.g. 'netapp' -> netapp.eightfold.ai),
    domain is the company's domain param (e.g. 'netapp.com')."""
    api_url = f"https://{slug}.eightfold.ai/api/apply/v2/jobs"

    jobs: list[Job] = []
    start = 0
    while True:
        resp = requests.get(api_url, params={"domain": domain, "start": start, "num": PAGE_SIZE}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        positions = data.get("positions", [])
        if not positions:
            break

        for entry in positions:
            locations = entry.get("locations") or [entry.get("location")]
            jobs.append(
                Job(
                    id=str(entry["id"]),
                    title=entry.get("name", "Unknown"),
                    company=company_name,
                    location=entry.get("location", "Unknown"),
                    url=entry.get("canonicalPositionUrl"),
                    posted_at=str(entry.get("t_create")) if entry.get("t_create") else None,
                    country=detect_country(locations),
                )
            )

        start += PAGE_SIZE
        if start >= data.get("count", 0):
            break

    return jobs
