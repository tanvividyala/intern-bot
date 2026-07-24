import requests

from adapters.base import Job


def send(webhook_url: str, job: Job) -> None:
    embed = {
        "title": job.title,
        "url": job.url,
        "color": 0x5865F2,
        "fields": [
            {"name": "Company", "value": job.company, "inline": True},
            {"name": "Location", "value": job.location, "inline": True},
        ],
    }
    resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
    resp.raise_for_status()
