from __future__ import annotations

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.models import CampaignContext


class IcpPlannerAgent:
    """Compatibility wrapper around the dynamic Campaign Strategy Agent."""

    name = "icp_planner_agent"

    def __init__(self) -> None:
        self.strategy = CampaignStrategyAgent()

    def plan(self, prompt: str) -> CampaignContext:
        campaign, _spec = self.strategy.plan(prompt)
        return campaign
