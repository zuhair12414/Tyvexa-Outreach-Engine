from __future__ import annotations

from cold_outreach_engine.models import CampaignContext, LeadMemory


class CompetitorGapAgent:
    """Compatibility placeholder. Use MarketContextAgent for the active pipeline."""

    name = "competitor_gap_agent"

    def run(self, campaign: CampaignContext, lead: LeadMemory) -> str:
        locality = ", ".join(part for part in [lead.city, lead.country] if part)
        target = lead.industry or ", ".join(campaign.industries)
        return (
            "needs_enrichment: market context should compare "
            f"{lead.company_name} against {target} alternatives in {locality or 'the campaign market'}."
        )
