from __future__ import annotations

from cold_outreach_engine.models import CampaignContext, Evidence, LeadMemory


class CompetitorGapAgent:
    name = "competitor_gap_agent"

    def run(self, campaign: CampaignContext, lead: LeadMemory) -> str:
        if not lead.city or not lead.industry:
            lead.open_questions.append("Local competitor comparison needs city and industry.")
            return "unknown: missing locality or industry"

        claim = (
            f"Competitor gap should be checked against nearby {lead.industry} businesses in "
            f"{lead.city}; v1 placeholder until search provider is connected."
        )
        lead.evidence.append(
            Evidence(
                claim=claim,
                source_url="system://competitor-gap-placeholder",
                agent=self.name,
                confidence=0.3,
            )
        )
        return "placeholder_gap: compare local competitors once web search is enabled"

