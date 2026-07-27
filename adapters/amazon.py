import requests

from adapters.base import Job

SEARCH_API = "https://www.amazon.jobs/en/search.json"
PAGE_SIZE = 100
# amazon.jobs's full-text search is a single global index (not per-company like the other
# ATSes), so there's no "list every job" mode -- we have to search for candidate terms.
# Querying "internship" pulls in thousands of unrelated postings (their descriptions mention
# internship eligibility in the boilerplate), so we search on the tighter terms instead and
# let main.py's title regex do the final filtering.
QUERIES = ["intern", "co-op"]


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    """slug is unused: amazon.jobs is Amazon's single global career site, not a
    multi-tenant ATS, so there's no per-company board to key off of."""
    by_id: dict[str, Job] = {}

    for query in QUERIES:
        offset = 0
        while True:
            resp = requests.get(
                SEARCH_API,
                params={"base_query": query, "offset": offset, "result_limit": PAGE_SIZE, "sort": "recent"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("jobs") or []
            if not entries:
                break

            for entry in entries:
                job_id = str(entry["id_icims"])
                if job_id in by_id:
                    continue
                country_code = entry.get("country_code")
                by_id[job_id] = Job(
                    id=job_id,
                    title=entry["title"],
                    company=company_name,
                    location=entry.get("normalized_location", "Unknown"),
                    url=f"https://www.amazon.jobs{entry['job_path']}",
                    posted_at=entry.get("posted_date"),
                    country="US" if country_code == "USA" else country_code,
                )

            offset += PAGE_SIZE
            if offset >= data.get("hits", 0):
                break

    return list(by_id.values())
