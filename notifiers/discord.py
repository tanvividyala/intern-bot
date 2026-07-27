import time

import requests

from adapters.base import Job

MAX_RETRIES = 3


def send(webhook_url: str, job: Job, logo_url: str | None = None) -> None:
    embed = {
        "title": job.title,
        "url": job.url,
        "color": 0x5865F2,
        "fields": [
            {"name": "Company", "value": job.company, "inline": True},
            {"name": "Location", "value": job.location, "inline": True},
        ],
    }
    if logo_url:
        embed["thumbnail"] = {"url": logo_url}

    for attempt in range(MAX_RETRIES):
        resp = requests.post(webhook_url, json={"embeds": [embed]}, timeout=15)
        # Webhooks get rate-limited easily when a run has many new jobs to announce at once
        # (e.g. a newly added adapter's first pass); back off and retry rather than dropping
        # the notification and letting the caller's exception handling mark it seen anyway.
        if resp.status_code == 429 and attempt < MAX_RETRIES - 1:
            retry_after = resp.json().get("retry_after", 1)
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        return
