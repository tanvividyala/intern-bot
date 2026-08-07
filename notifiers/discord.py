import time

import requests

from adapters.base import Job

MAX_RETRIES = 3


def send(webhook_url: str, job: Job, logo_url: str | None = None) -> None:
    embed = {
        # Author renders above the title in bold, so it reads as the largest text next to the
        # role name itself -- Discord embeds have no font-size control, this is the closest we
        # get to putting the company name "almost as big as" the title.
        "author": {"name": job.company, "icon_url": logo_url} if logo_url else {"name": job.company},
        "title": job.title,
        "url": job.url,
        "color": 0x5865F2,
        "fields": [
            {"name": "Location", "value": job.location, "inline": True},
        ],
    }

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
