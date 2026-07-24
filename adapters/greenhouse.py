import requests

from adapters.base import Job
from adapters.us_location import detect_country

BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


def _job_country(entry: dict) -> str | None:
    candidates = [(entry.get("location") or {}).get("name")]
    for office in entry.get("offices") or []:
        candidates.append(office.get("name"))
        candidates.append(office.get("location"))
    return detect_country(candidates)


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
                country=_job_country(entry),
            )
        )
    return jobs
