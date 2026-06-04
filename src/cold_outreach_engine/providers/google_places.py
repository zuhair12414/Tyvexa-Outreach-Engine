from __future__ import annotations

import httpx

from cold_outreach_engine.models import CampaignContext, CampaignSpec
from cold_outreach_engine.providers.base import CandidateCompany


class GooglePlacesProvider:
    endpoint = "https://places.googleapis.com/v1/places:searchText"

    def __init__(self, api_key: str, max_results_per_query: int = 20) -> None:
        self.api_key = api_key
        self.max_results_per_query = max_results_per_query

    def search_companies(
        self, campaign: CampaignContext, spec: CampaignSpec | None = None
    ) -> list[CandidateCompany]:
        candidates: list[CandidateCompany] = []
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "places.displayName,places.formattedAddress,places.nationalPhoneNumber,"
                "places.websiteUri,places.types"
            ),
        }
        with httpx.Client(timeout=20) as client:
            for query in self._queries_for(campaign, spec):
                response = client.post(
                    self.endpoint,
                    headers=headers,
                    json={"textQuery": query, "pageSize": self.max_results_per_query},
                )
                response.raise_for_status()
                data = response.json()
                for place in data.get("places", []):
                    name = place.get("displayName", {}).get("text") or "Unknown place"
                    website = place.get("websiteUri")
                    candidates.append(
                        CandidateCompany(
                            name=name,
                            country=campaign.countries[0] if campaign.countries else None,
                            industry=campaign.industries[0] if campaign.industries else None,
                            website=website,
                            source_url=website or "google_places://text_search",
                            snippets=[
                                place.get("formattedAddress", ""),
                                f"Phone: {place.get('nationalPhoneNumber', '')}",
                                f"Types: {', '.join(place.get('types', []))}",
                            ],
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
                queries.append(f"{industry} {country}")
        return queries[:6]
