import requests

from adapters.base import Job

PAGE_SIZE = 20


def fetch_jobs(slug: str, company_name: str, tenant: str, site: str) -> list[Job]:
    """slug is the Workday tenant subdomain (e.g. 'salesforce' -> salesforce.wd12.myworkdayjobs.com)."""
    url = f"https://{slug}.{tenant}.myworkdayjobs.com/wday/cxs/{slug}/{site}/jobs"

    jobs: list[Job] = []
    offset = 0
    while True:
        resp = requests.post(
            url,
            json={"appliedFacets": {}, "limit": PAGE_SIZE, "offset": offset, "searchText": ""},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        postings = data.get("jobPostings", [])
        if not postings:
            break

        for entry in postings:
            path = entry["externalPath"]
            jobs.append(
                Job(
                    id=path,
                    title=entry["title"],
                    company=company_name,
                    location=entry.get("locationsText", "Unknown"),
                    url=f"https://{slug}.{tenant}.myworkdayjobs.com/{site}{path}",
                    posted_at=entry.get("postedOn"),
                )
            )

        offset += PAGE_SIZE
        if offset >= data.get("total", 0):
            break

    return jobs
