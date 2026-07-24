import requests

from adapters.base import Job

BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    resp = requests.get(BOARDS_API.format(slug=slug), params={"content": "true"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for entry in data.get("jobs", []):
        jobs.append(
            Job(
                id=str(entry["id"]),
                title=entry["title"],
                company=company_name,
                location=(entry.get("location") or {}).get("name", "Unknown"),
                url=entry["absolute_url"],
                posted_at=entry.get("first_published"),
            )
        )
    return jobs
