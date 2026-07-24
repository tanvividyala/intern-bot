import requests

from adapters.base import Job

PAGE_SIZE = 500


def fetch_jobs(slug: str, company_name: str, host: str, site_number: str, site_alias: str) -> list[Job]:
    """Oracle Fusion Recruiting Cloud (Oracle Recruiting Cloud / HCM). `host` is the
    tenant's Fusion instance (e.g. 'eeho.fa.us2.oraclecloud.com'), `site_number` is the
    internal career-site id (e.g. 'CX_1001'), `site_alias` is the public URL slug
    (e.g. 'jobsearch')."""
    api_url = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"

    jobs: list[Job] = []
    offset = 0
    while True:
        resp = requests.get(
            api_url,
            params={
                "onlyData": "true",
                "expand": "requisitionList",
                "limit": PAGE_SIZE,
                "finder": f"findReqs;siteNumber={site_number},limit={PAGE_SIZE},offset={offset},sortBy=POSTING_DATES_DESC",
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        search = data["items"][0]
        requisitions = search.get("requisitionList") or []
        if not requisitions:
            break

        for entry in requisitions:
            jobs.append(
                Job(
                    id=str(entry["Id"]),
                    title=entry["Title"],
                    company=company_name,
                    location=entry.get("PrimaryLocation", "Unknown"),
                    url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site_alias}/job/{entry['Id']}",
                    posted_at=entry.get("PostedDate"),
                    country=entry.get("PrimaryLocationCountry"),
                )
            )

        offset += PAGE_SIZE
        if offset >= search.get("TotalJobsCount", 0):
            break

    return jobs
