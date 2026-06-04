from __future__ import annotations

import httpx

from cold_outreach_engine.models import CampaignContext, CampaignSpec
from cold_outreach_engine.providers.base import CandidateCompany


class BraveSearchProvider:
    endpoint = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str, max_results_per_query: int = 10) -> None:
        self.api_key = api_key
        self.max_results_per_query = max_results_per_query

    def search_companies(
        self, campaign: CampaignContext, spec: CampaignSpec | None = None
    ) -> list[CandidateCompany]:
        candidates: list[CandidateCompany] = []
        queries = self._queries_for(campaign, spec)
        with httpx.Client(timeout=20) as client:
            for query in queries:
                response = client.get(
                    self.endpoint,
                    params={"q": query, "count": self.max_results_per_query},
                    headers={"x-subscription-token": self.api_key},
                )
                response.raise_for_status()
                data = response.json()
                for result in data.get("web", {}).get("results", []):
                    url = result.get("url")
                    title = result.get("title") or url or "Unknown company"
                    candidates.append(
                        CandidateCompany(
                            name=self._clean_title(title),
                            country=campaign.countries[0] if campaign.countries else None,
                            industry=campaign.industries[0] if campaign.industries else None,
                            website=url,
                            source_url=url,
                            snippets=[result.get("description", "")],
                        )
                    )
        return candidates

    def _queries_for(
        self, campaign: CampaignContext, spec: CampaignSpec | None = None
    ) -> list[str]:
        if spec and spec.search_queries:
            return spec.search_queries[:6]
        queries = []
        for country in campaign.countries:
            for industry in campaign.industries:
                queries.append(f'{industry} "{country}" {campaign.offer}')
                queries.append(f'{industry} "{country}" official website contact')
        return queries[:6]

    def _clean_title(self, title: str) -> str:
        return title.split("|")[0].split("-")[0].strip()
