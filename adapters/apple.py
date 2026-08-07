import requests

from adapters.base import Job

CSRF_URL = "https://jobs.apple.com/api/v1/CSRFToken"
SEARCH_URL = "https://jobs.apple.com/api/v1/search"
PAGE_SIZE = 20
DATE_FORMAT = {"longDate": "MMMM D, YYYY", "mediumDate": "MMM D, YYYY"}
US_COUNTRY_ID = "iso-country-USA"
# Like Amazon, jobs.apple.com is a single global site with a fuzzy full-text search rather
# than a per-company board. "internship"/"co-op" alone occasionally miss bare-"Intern"-titled
# postings (e.g. "Intern Program") since Apple's relevance ranking doesn't always surface them
# for those queries. "intern" alone pulls in ~1,800 mostly-unrelated hits (heavy stemming/
# boilerplate matching over ~90 pages), but that's fine: main.py's title regex uses a \bintern\b
# word boundary, so noise like "Internal"/"International" is filtered out downstream anyway.
QUERIES = ["internship", "co-op", "intern"]


def _job_country(entry: dict) -> str | None:
    locations = entry.get("locations") or []
    if any(loc.get("countryID") == US_COUNTRY_ID for loc in locations):
        return "US"
    if locations:
        return locations[0].get("countryName")
    return None


def _job_location(entry: dict) -> str:
    parts = []
    for loc in entry.get("locations") or []:
        if loc.get("city"):
            segment = loc["city"]
            if loc.get("stateProvince"):
                segment += f", {loc['stateProvince']}"
        else:
            segment = loc.get("name") or loc.get("countryName") or "Unknown"
        parts.append(segment)
    return "; ".join(parts) if parts else "Unknown"


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    """slug is unused: jobs.apple.com is Apple's single global career site, not a
    multi-tenant ATS, so there's no per-company board to key off of."""
    session = requests.Session()
    token_resp = session.get(CSRF_URL, timeout=30)
    token_resp.raise_for_status()
    csrf_token = token_resp.headers.get("X-Apple-CSRF-Token")
    if not csrf_token:
        raise RuntimeError("Apple CSRF token missing from response headers")
    session.headers["X-Apple-CSRF-Token"] = csrf_token

    by_id: dict[str, Job] = {}

    for query in QUERIES:
        page = 1
        while True:
            resp = session.post(
                SEARCH_URL,
                json={"query": query, "filters": {}, "page": page, "locale": "en-us", "sort": "newest", "format": DATE_FORMAT},
                timeout=30,
            )
            resp.raise_for_status()
            result = resp.json()["res"]
            entries = result.get("searchResults") or []
            if not entries:
                break

            for entry in entries:
                job_id = entry["id"]
                if job_id in by_id:
                    continue
                by_id[job_id] = Job(
                    id=job_id,
                    title=entry["postingTitle"],
                    company=company_name,
                    location=_job_location(entry),
                    url=f"https://jobs.apple.com/en-us/details/{entry['positionId']}/{entry['transformedPostingTitle']}",
                    posted_at=entry.get("postDateInGMT"),
                    country=_job_country(entry),
                )

            page += 1
            if (page - 1) * PAGE_SIZE >= result.get("totalRecords", 0):
                break

    return list(by_id.values())
