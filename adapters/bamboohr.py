import requests

from adapters.base import Job
from adapters.us_location import detect_country

LIST_API = "https://{slug}.bamboohr.com/careers/list"


def _job_country(entry: dict) -> str | None:
    ats_location = entry.get("atsLocation") or {}
    location = entry.get("location") or {}
    candidates = [
        ats_location.get("country"),
        ats_location.get("state"),
        ats_location.get("city"),
        location.get("state"),
        location.get("city"),
    ]
    return detect_country(candidates)


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    """slug is the BambooHR subdomain (e.g. 'carlsmed' -> carlsmed.bamboohr.com).

    The list endpoint mostly leaves atsLocation empty (only 'location' city/state), so
    country is best-effort via the same US-location heuristic other ATSes fall back to.
    No posted-date field is exposed.
    """
    resp = requests.get(LIST_API.format(slug=slug), timeout=30)
    resp.raise_for_status()
    data = resp.json()

    jobs = []
    for entry in data.get("result", []):
        location = entry.get("location") or {}
        parts = [p for p in (location.get("city"), location.get("state")) if p]
        jobs.append(
            Job(
                id=str(entry["id"]),
                title=entry["jobOpeningName"],
                company=company_name,
                location=", ".join(parts) if parts else "Unknown",
                url=f"https://{slug}.bamboohr.com/careers/{entry['id']}",
                posted_at=None,
                country=_job_country(entry),
            )
        )
    return jobs
