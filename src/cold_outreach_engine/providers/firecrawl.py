from __future__ import annotations

import httpx

from cold_outreach_engine.providers.base import CandidateCompany, PageSnapshot


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

