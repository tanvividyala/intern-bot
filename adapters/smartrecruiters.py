import requests

from adapters.base import Job

POSTINGS_API = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"
PAGE_SIZE = 100


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    jobs: list[Job] = []
    offset = 0
    while True:
        resp = requests.get(
            POSTINGS_API.format(slug=slug),
            params={"limit": PAGE_SIZE, "offset": offset},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        postings = data.get("content", [])
        if not postings:
            break

        for entry in postings:
            location = entry.get("location") or {}
            country = location.get("country")
            jobs.append(
                Job(
                    id=str(entry["id"]),
                    title=entry["name"],
                    company=company_name,
                    location=location.get("fullLocation", "Unknown"),
                    url=f"https://jobs.smartrecruiters.com/{slug}/{entry['id']}",
                    posted_at=entry.get("releasedDate"),
                    country=country.upper() if country else None,
                )
            )

        offset += PAGE_SIZE
        if offset >= data.get("totalFound", 0):
            break

    return jobs
