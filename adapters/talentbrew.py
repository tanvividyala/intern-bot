import json
import re
import xml.etree.ElementTree as ET
from urllib.parse import unquote

import requests

from adapters.base import Job
from adapters.us_location import detect_country

SITEMAP_NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
LD_JSON_RE = re.compile(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', re.DOTALL)


def fetch_jobs(slug: str, company_name: str) -> list[Job]:
    """slug is the careers host (e.g. 'jobs.intuit.com').

    TalentBrew has no public jobs API, and its search pages are disallowed by robots.txt, so
    listings come from the sitemap (which robots.txt does allow, as it does the /job/ pages).
    The sitemap only carries the job URL, whose slug is a lossy form of the title (punctuation
    dropped, 'co-op' -> 'co op'), so title and location here are approximate — `fetch_details`
    reads the real ones off the job page for listings that pass the keyword filter.
    """
    job_url_re = re.compile(rf"^https://{re.escape(slug)}/job/([^/]+)/([^/]+)/\d+/(\d+)/?$")

    jobs: list[Job] = []
    for url in _sitemap_urls(f"https://{slug}/sitemap.xml"):
        match = job_url_re.match(url)
        if not match:
            continue
        city, title, job_id = match.groups()
        jobs.append(
            Job(
                id=job_id,
                title=_unslug(title),
                company=company_name,
                location=_unslug(city),
                url=url,
                posted_at=None,
            )
        )

    return jobs


def fetch_details(job: Job, slug: str) -> dict:
    """Real title, location and posting date from the job page's JSON-LD JobPosting."""
    resp = requests.get(job.url, timeout=30)
    resp.raise_for_status()
    posting = _job_posting(resp.text)
    if posting is None:
        return {}

    places = posting.get("jobLocation") or []
    locations = [_address_text(place.get("address") or {}) for place in _as_list(places)]
    locations = [location for location in locations if location]

    details = {"country": detect_country(locations)}
    if posting.get("title"):
        details["title"] = posting["title"]
    if locations:
        details["location"] = "; ".join(locations)
    if posting.get("datePosted"):
        details["posted_at"] = posting["datePosted"]
    return details


def _sitemap_urls(sitemap_url: str) -> list[str]:
    resp = requests.get(sitemap_url, timeout=30)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    if root.tag.endswith("sitemapindex"):
        urls: list[str] = []
        for loc in root.findall("sm:sitemap/sm:loc", SITEMAP_NS):
            urls.extend(_sitemap_urls(loc.text.strip()))
        return urls

    return [loc.text.strip() for loc in root.findall("sm:url/sm:loc", SITEMAP_NS) if loc.text]


def _unslug(text: str) -> str:
    return re.sub(r"-+", " ", unquote(text)).strip().title()


def _as_list(value):
    return value if isinstance(value, list) else [value]


def _address_text(address: dict) -> str:
    """'Mountain View, California, United States' from a schema.org PostalAddress."""
    country = address.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name")
    parts = (address.get("addressLocality"), address.get("addressRegion"), country)
    return ", ".join(part for part in parts if part)


def _job_posting(html: str) -> dict | None:
    for block in LD_JSON_RE.findall(html):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        for entry in _as_list(data):
            if isinstance(entry, dict) and entry.get("@type") == "JobPosting":
                return entry
    return None
