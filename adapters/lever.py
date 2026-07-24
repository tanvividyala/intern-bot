import requests

from adapters.base import Job
from adapters.us_location import detect_country

POSTINGS_API = "https://api.lever.co/v0/postings/{slug}"


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    resp = requests.get(POSTINGS_API.format(slug=slug), params={"mode": "json"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for entry in data:
        categories = entry.get("categories") or {}
        country = entry.get("country")
        if not country:
            candidates = [categories.get("location")] + (categories.get("allLocations") or [])
            country = detect_country(candidates)
        elif country.upper() != "US":
            country = country.upper()
        else:
            country = "US"

        jobs.append(
            Job(
                id=entry["id"],
                title=entry["text"],
                company=company_name,
                location=categories.get("location", "Unknown"),
                url=entry.get("hostedUrl"),
                posted_at=str(entry.get("createdAt")) if entry.get("createdAt") else None,
                country=country,
            )
        )
    return jobs
