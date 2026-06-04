from __future__ import annotations

import httpx

from cold_outreach_engine.models import CampaignContext
from cold_outreach_engine.providers.base import CandidateCompany, PageSnapshot


class FirecrawlSearchProvider:
    endpoint = "https://api.firecrawl.dev/v2/search"

    def __init__(self, api_key: str, max_results_per_query: int = 5) -> None:
        self.api_key = api_key
        self.max_results_per_query = max_results_per_query

    def search_companies(self, campaign: CampaignContext) -> list[CandidateCompany]:
        candidates: list[CandidateCompany] = []
        with httpx.Client(timeout=30) as client:
            for query in self._queries_for(campaign):
                response = client.post(
                    self.endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"query": query, "limit": self.max_results_per_query},
                )
                response.raise_for_status()
                data = response.json()
                for result in self._results_from(data):
                    url = result.get("url")
                    title = result.get("title") or url or "Unknown company"
                    candidates.append(
                        CandidateCompany(
                            name=self._clean_title(title),
                            country=campaign.countries[0] if campaign.countries else None,
                            industry=campaign.industries[0] if campaign.industries else None,
                            website=url,
                            source_url=url or "firecrawl://search",
                            snippets=[
                                result.get("description") or result.get("markdown") or ""
                            ],
                        )
                    )
        return candidates

    def _queries_for(self, campaign: CampaignContext) -> list[str]:
        queries = []
        for country in campaign.countries:
            for industry in campaign.industries:
                queries.append(f"{industry} {country} official website contact phone")
                queries.append(f"{industry} {country} reservations support customer service")
        return queries[:6]

    def _results_from(self, data: dict) -> list[dict]:
        if isinstance(data.get("data"), list):
            return data["data"]
        if isinstance(data.get("results"), list):
            return data["results"]
        return []

    def _clean_title(self, title: str) -> str:
        return title.split("|")[0].split("-")[0].strip()


class FirecrawlProvider:
    endpoint = "https://api.firecrawl.dev/v2/scrape"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def crawl_company(self, company: CandidateCompany) -> list[PageSnapshot]:
        if not company.website:
            return []
        with httpx.Client(timeout=45) as client:
            response = client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "url": company.website,
                    "formats": ["markdown"],
                    "onlyMainContent": True,
                    "removeBase64Images": True,
                    "blockAds": True,
                },
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            metadata = data.get("metadata", {})
            text = data.get("markdown") or data.get("content") or ""
            if not text:
                return []
            return [
                PageSnapshot(
                    url=company.website,
                    title=metadata.get("title") or company.name,
                    text=text[:8000],
                )
            ]
