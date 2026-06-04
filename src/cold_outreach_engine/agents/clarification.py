from __future__ import annotations

from cold_outreach_engine.models import (
    CampaignContext,
    CampaignSpec,
    ClarificationQuestion,
    LeadAssessment,
    LeadMemory,
    LeadScore,
    LeadStatus,
)


class ClarificationAgent:
    name = "clarification_agent"

    def run(
        self,
        campaign: CampaignContext,
        lead: LeadMemory,
        score: LeadScore | LeadAssessment,
        spec: CampaignSpec | None = None,
    ) -> ClarificationQuestion | None:
        if spec and "unspecified" in " ".join(spec.countries + spec.target_industries).lower():
            return ClarificationQuestion(
                campaign_id=campaign.id,
                lead_id=None,
                scope="campaign_wide",
                question=(
                    "The campaign target is underspecified. Which country, region, "
                    "or buyer segment should this run prioritize?"
                ),
            )

        if score.status == LeadStatus.NEEDS_INPUT:
            return ClarificationQuestion(
                campaign_id=campaign.id,
                lead_id=lead.id,
                scope="lead_specific",
                question=(
                    f"{lead.company_name} has some fit but weak public evidence. "
                    "Should this lead stay in manual review, or should similar low-signal leads be rejected?"
                ),
            )

        if score.status == LeadStatus.MANUAL_REVIEW and not lead.socials:
            return ClarificationQuestion(
                campaign_id=campaign.id,
                lead_id=None,
                scope="campaign_wide",
                question=(
                    "For this campaign, should missing socials be a rejection reason, "
                    "or only a lower-confidence signal when website/contact evidence exists?"
                ),
            )

        return None
