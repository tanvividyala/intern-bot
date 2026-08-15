import re

import requests
from xml.etree import ElementTree as ET

from adapters.base import Job
from adapters.us_location import text_indicates_us

ATOM_NS = "{http://www.w3.org/2005/Atom}"
XHTML_NS = "{http://www.w3.org/1999/xhtml}"
_FIELD_RE = re.compile(r"^(Program ID|Title|City|Program country):(.*)$")


def fetch_jobs(slug: str, company_name: str, vacancy_ids: list[int]) -> list[Job]:
    """slug is the Oleeo/tal.net careers host (e.g. 'bankcampuscareers.tal.net'). Each job-board
    category has a numeric id and its own Atom feed at
    `/vx/mobile-0/candidate/jobboard/vacancy/<id>/feed` -- no login required. Oleeo mixes actual
    postings with recruiting-event listings across different category ids on the same board, so
    `vacancy_ids` must be picked by checking each `/vx/.../jobboard/vacancy/<id>/adv/` page (or its
    feed) in a browser and keeping only the ones that list programs/roles, not events.
    """
    jobs: list[Job] = []
    for vacancy_id in vacancy_ids:
        resp = requests.get(
            f"https://{slug}/vx/mobile-0/candidate/jobboard/vacancy/{vacancy_id}/feed", timeout=30
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)

        for entry in root.findall(f"{ATOM_NS}entry"):
            fields = _parse_fields(entry)
            program_id = fields.get("Program ID")
            if not program_id:
                continue

            link_el = entry.find(f"{ATOM_NS}link")
            city = fields.get("City", "")
            country_field = fields.get("Program country", "")
            if text_indicates_us(country_field):
                country = "US"
            else:
                country = country_field or None
            jobs.append(
                Job(
                    id=program_id,
                    title=fields.get("Title", "Unknown"),
                    company=company_name,
                    location=city or country_field or "Unknown",
                    url=link_el.get("href") if link_el is not None else None,
                    posted_at=entry.findtext(f"{ATOM_NS}published"),
                    country=country,
                )
            )

    return jobs


def _parse_fields(entry) -> dict[str, str]:
    div = entry.find(f"{ATOM_NS}content/{XHTML_NS}div")
    if div is None:
        return {}
    fields: dict[str, str] = {}
    for line in "".join(div.itertext()).splitlines():
        match = _FIELD_RE.match(line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return fields
