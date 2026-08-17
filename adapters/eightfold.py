import time

import requests

from adapters.base import Job
from adapters.us_location import detect_country

PAGE_SIZE = 10
MAX_RETRIES = 3


def fetch_jobs(slug: str, company_name: str, domain: str, host: str | None = None, api: str = "apply") -> list[Job]:
    """slug is the Eightfold tenant subdomain (e.g. 'netapp' -> netapp.eightfold.ai),
    domain is the company's domain param (e.g. 'netapp.com').

    `host` overrides that hostname for companies serving Eightfold from their own careers
    domain, and `api` picks the endpoint: 'apply' (the public jobs API) or 'pcsx' (the search
    API the careers UI itself calls). Some tenants lock down the apply API but leave pcsx
    open — see the README.
    """
    host = host or f"{slug}.eightfold.ai"
    if api not in ENDPOINTS:
        raise ValueError(f"Unknown Eightfold api {api!r}, expected one of {sorted(ENDPOINTS)}")
    path, unpack, to_job = ENDPOINTS[api]
    api_url = f"https://{host}{path}"

    jobs: list[Job] = []
    start = 0
    while True:
        for attempt in range(MAX_RETRIES):
            resp = requests.get(api_url, params={"domain": domain, "start": start, "num": PAGE_SIZE}, timeout=30)
            # Large boards paginate in runs of hundreds of requests (Eightfold's page size caps
            # at 10 regardless of `num`), which routinely trips per-IP rate limiting partway
            # through -- back off and retry rather than dropping the rest of the board.
            if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(int(resp.headers.get("Retry-After", 2)) * (attempt + 1))
                continue
            break
        resp.raise_for_status()
        positions, total = unpack(resp.json())
        if not positions:
            break

        jobs.extend(to_job(entry, company_name, host) for entry in positions)

        start += PAGE_SIZE
        if start >= total:
            break

    return jobs


def _unpack_apply(payload: dict) -> tuple[list[dict], int]:
    return payload.get("positions", []), payload.get("count", 0)


def _unpack_pcsx(payload: dict) -> tuple[list[dict], int]:
    data = payload.get("data", {})
    return data.get("positions", []), data.get("count", 0)


def _job_from_apply(entry: dict, company_name: str, host: str) -> Job:
    locations = entry.get("locations") or [entry.get("location")]
    return Job(
        id=str(entry["id"]),
        title=entry.get("name", "Unknown"),
        company=company_name,
        location=entry.get("location", "Unknown"),
        url=entry.get("canonicalPositionUrl"),
        posted_at=str(entry.get("t_create")) if entry.get("t_create") else None,
        country=detect_country(locations),
    )


def _job_from_pcsx(entry: dict, company_name: str, host: str) -> Job:
    """pcsx returns the same listings under different field names, and a relative job URL."""
    locations = entry.get("locations") or []
    path = entry.get("positionUrl") or f"/careers/job/{entry['id']}"
    return Job(
        id=str(entry["id"]),
        title=entry.get("name", "Unknown"),
        company=company_name,
        location="; ".join(locations) or "Unknown",
        url=f"https://{host}{path}",
        posted_at=str(entry.get("postedTs")) if entry.get("postedTs") else None,
        country=detect_country(locations),
    )


ENDPOINTS = {
    "apply": ("/api/apply/v2/jobs", _unpack_apply, _job_from_apply),
    "pcsx": ("/api/pcsx/search", _unpack_pcsx, _job_from_pcsx),
}
