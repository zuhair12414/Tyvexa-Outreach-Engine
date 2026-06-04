from __future__ import annotations

from cold_outreach_engine.models import CampaignContext, Evidence, LeadMemory
from cold_outreach_engine.providers.base import SearchProvider


class LeadDiscoveryAgent:
    name = "lead_discovery_agent"

    def __init__(self, search_provider: SearchProvider) -> None:
        self.search_provider = search_provider

    def run(self, campaign: CampaignContext) -> list[LeadMemory]:
        leads: list[LeadMemory] = []
        for candidate in self.search_provider.search_companies(campaign):
            evidence = []
            if candidate.source_url:
                evidence.append(
                    Evidence(
                        claim="Candidate discovered from configured search provider.",
                        source_url=candidate.source_url,
                        agent=self.name,
                        confidence=0.6,
                    )
                )
            lead = LeadMemory(
                campaign_id=campaign.id,
                company_name=candidate.name,
                country=candidate.country,
                city=candidate.city,
                industry=candidate.industry,
                website=candidate.website,
                facts=candidate.snippets,
                evidence=evidence,
            )
            leads.append(lead)
        return leads

