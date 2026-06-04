from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from cold_outreach_engine.models import CampaignContext


@dataclass
class CandidateCompany:
    name: str
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    website: str | None = None
    source_url: str | None = None
    snippets: list[str] = field(default_factory=list)


@dataclass
class PageSnapshot:
    url: str
    title: str
    text: str


class SearchProvider(Protocol):
    def search_companies(self, campaign: CampaignContext) -> list[CandidateCompany]:
        """Return candidate companies. This must not scrape LinkedIn."""


class CrawlProvider(Protocol):
    def crawl_company(self, company: CandidateCompany) -> list[PageSnapshot]:
        """Return public website pages for the company."""


class LlmProvider(Protocol):
    def classify(self, task: str, payload: dict) -> dict:
        """Return structured classification JSON for an agent task."""

