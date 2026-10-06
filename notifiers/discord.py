import datetime
import re
import time

import requests

from adapters.base import Job

MAX_RETRIES = 3

# Epoch values at or above this are milliseconds, not seconds -- 1e11 seconds is the year 5138,
# so nothing an ATS reports as a post date can legitimately be a second-count that large.
EPOCH_MS_THRESHOLD = 10**11

# Human-written date formats a few ATSes return instead of ISO 8601 (Amazon renders
# "September  9, 2026" with the day padded, which is why whitespace is collapsed before parsing).
TEXT_DATE_FORMATS = ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%d %B %Y")


def _parse_posted_at(raw: str) -> datetime.datetime | None:
    """Best-effort parse of the wildly inconsistent `posted_at` values the adapters produce.

    Across ATSes this arrives as an ISO 8601 string with an offset (Greenhouse, Ashby,
    SmartRecruiters, Oracle, Oleeo, TalentBrew, Apple, Google), an epoch count in either seconds
    or milliseconds (Lever, Eightfold), or a pre-rendered relative phrase like "Posted Today"
    (Workday) that holds no parseable date at all. Returns None for that last group so the caller
    can fall back to showing the text as-is.
    """
    value = raw.strip()
    if not value:
        return None

    if value.lstrip("-").isdigit():
        epoch = int(value)
        if abs(epoch) >= EPOCH_MS_THRESHOLD:
            epoch /= 1000
        try:
            return datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    try:
        # fromisoformat only learned to accept a trailing "Z" in 3.11; normalize it so this works
        # on older runtimes too.
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        parsed = _parse_text_date(value)
        if parsed is None:
            return None
    # A timestamp with no offset (some Oracle/iCIMS responses) is treated as UTC rather than the
    # runner's local zone, so the rendered date doesn't shift with wherever the job happens to run.
    return parsed.replace(tzinfo=datetime.timezone.utc) if parsed.tzinfo is None else parsed


def _parse_text_date(value: str) -> datetime.datetime | None:
    collapsed = re.sub(r"\s+", " ", value)
    for fmt in TEXT_DATE_FORMATS:
        try:
            return datetime.datetime.strptime(collapsed, fmt)
        except ValueError:
            continue
    return None


def format_posted_at(raw: str | None) -> str | None:
    """Renders `posted_at` for the embed, or None when there's nothing worth showing."""
    if not raw:
        return None

    parsed = _parse_posted_at(raw)
    if parsed is None:
        return raw.strip() or None  # e.g. Workday's "Posted Today" -- already human-readable

    # Discord renders these client-side in each viewer's own timezone and locale: an absolute
    # date plus the relative form, which is the part that actually matters when triaging a
    # listing ("3 days ago" vs "8 months ago").
    epoch = int(parsed.timestamp())
    return f"<t:{epoch}:D> (<t:{epoch}:R>)"


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

    # Not every ATS reports a post date (BambooHR never does, and enrichment can fail), so this
    # field is added only when there's a value -- an empty embed field is a Discord API error.
    posted = format_posted_at(job.posted_at)
    if posted:
        embed["fields"].append({"name": "Posted", "value": posted, "inline": True})

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
