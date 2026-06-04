from __future__ import annotations

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.models import CampaignContext, SourcePlan


class SourceRouterAgent:
    """Compatibility wrapper that exposes the strategy spec as a source plan."""

    name = "source_router_agent"

    def __init__(self) -> None:
        self.strategy = CampaignStrategyAgent()

    def run(self, campaign: CampaignContext) -> SourcePlan:
        spec = self.strategy.build_spec(campaign)
        return SourcePlan(
            campaign_id=campaign.id,
            sources=spec.source_priorities,
            search_queries=spec.search_queries,
            rationale=(
                "Source plan generated from the campaign operating spec; "
                "it is not a fixed industry profile."
            ),
        )
