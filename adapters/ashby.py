import requests

from adapters.base import Job

JOB_BOARD_API = "https://api.ashbyhq.com/posting-api/job-board/{slug}"


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    resp = requests.get(JOB_BOARD_API.format(slug=slug), timeout=30)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for entry in data.get("jobs", []):
        address = (entry.get("address") or {}).get("postalAddress") or {}
        country_name = address.get("addressCountry")
        jobs.append(
            Job(
                id=str(entry["id"]),
                title=entry["title"],
                company=company_name,
                location=entry.get("location", "Unknown"),
                url=entry.get("jobUrl") or entry.get("applyUrl"),
                posted_at=entry.get("publishedAt"),
                country="US" if country_name == "United States" else country_name,
            )
        )
    return jobs
