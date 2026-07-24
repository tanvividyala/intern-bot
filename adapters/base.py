from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Job:
    id: str
    title: str
    company: str
    location: str
    url: str
    posted_at: str | None


class Adapter(Protocol):
    def fetch_jobs(self, slug: str, company_name: str) -> list[Job]: ...
