import requests

from adapters.base import Job

PAGE_SIZE = 20


def fetch_jobs(slug: str, company_name: str, tenant: str, site: str) -> list[Job]:
    """slug is the Workday tenant subdomain (e.g. 'salesforce' -> salesforce.wd12.myworkdayjobs.com).

    The search/list endpoint doesn't expose a structured country field, so `country` is left
    unset here. Use `fetch_country` to look it up per-job for candidates that already passed
    other filters (title keywords) to avoid an extra request per listing.
    """
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
            path = entry.get("externalPath")
            if not path:
                print(f"Skipping job posting without externalPath: {entry.get('title', 'Unknown')}")
                continue
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


def fetch_country(job: Job, slug: str, tenant: str, site: str) -> str | None:
    url = f"https://{slug}.{tenant}.myworkdayjobs.com/wday/cxs/{slug}/{site}{job.id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    info = resp.json().get("jobPostingInfo", {})
    country = (info.get("jobRequisitionLocation") or {}).get("country") or {}
    return country.get("alpha2Code")
