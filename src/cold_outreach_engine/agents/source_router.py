from __future__ import annotations

from cold_outreach_engine.models import CampaignContext, SourcePlan


class SourceRouterAgent:
    name = "source_router_agent"

    def run(self, campaign: CampaignContext) -> SourcePlan:
        industries = " ".join(campaign.industries).lower()
        sources = ["brave_search", "company_websites"]

        if any(term in industries for term in ["restaurant", "salon", "clinic", "local"]):
            sources = ["google_places", "google_reviews", "brave_search", "company_websites"]
        elif any(term in industries for term in ["bpo", "customer service", "call center"]):
            sources = ["brave_search", "industry_directories", "job_posts", "company_websites"]
        elif "insurance" in industries:
            sources = ["brave_search", "company_registries", "company_websites", "review_sites"]

        queries = []
        for country in campaign.countries:
            for industry in campaign.industries:
                queries.append(f"{industry} {country} {campaign.offer}")
                queries.append(f"{industry} {country} contact phone customer support")

        return SourcePlan(
            campaign_id=campaign.id,
            sources=sources,
            search_queries=queries[:12],
            rationale=(
                "Sources are routed by industry: local businesses use maps/reviews, "
                "BPO/service companies use web/directories/job signals."
            ),
        )

