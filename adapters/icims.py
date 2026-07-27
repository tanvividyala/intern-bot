import requests

from adapters.base import Job

PAGE_SIZE = 100


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    """slug is the careers host (e.g. 'careers.rivian.com'), an iCIMS-hosted careers site (the
    modern "Jibe" front end iCIMS acquired, not the legacy icims.com board). Its /api/jobs endpoint
    already exposes a structured country_code per listing, so no per-job enrichment is needed.
    """
    jobs: list[Job] = []
    page = 1
    while True:
        resp = requests.get(
            f"https://{slug}/api/jobs",
            params={"page": page, "limit": PAGE_SIZE},
            timeout=30,
        )
        resp.raise_for_status()
        postings = resp.json().get("jobs", [])
        if not postings:
            break

        for entry in postings:
            data = entry["data"]
            jobs.append(
                Job(
                    id=data["slug"],
                    title=data["title"],
                    company=company_name,
                    location=data.get("location_name", "Unknown"),
                    url=f"https://{slug}/jobs/{data['slug']}",
                    posted_at=data.get("posted_date"),
                    country=data.get("country_code"),
                )
            )

        page += 1

    return jobs
