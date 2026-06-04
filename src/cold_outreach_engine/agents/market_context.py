from __future__ import annotations

from cold_outreach_engine.models import (
    CampaignContext,
    CampaignSpec,
    Evidence,
    LeadAssessment,
    LeadMemory,
    MarketContext,
)


class MarketContextAgent:
    name = "market_context_agent"

    def run(
        self,
        campaign: CampaignContext,
        spec: CampaignSpec,
        lead: LeadMemory,
        assessment: LeadAssessment,
    ) -> MarketContext:
        locality = ", ".join(part for part in [lead.city, lead.country] if part)
        industry = lead.industry or (spec.target_industries[0] if spec.target_industries else "target segment")
        queries = self._competitor_queries(campaign, spec, lead, industry, locality)
        gap_hypotheses = self._gap_hypotheses(spec, assessment)

        evidence = Evidence(
            claim=(
                "Market context queued for enrichment using campaign-specific competitor "
                "and alternative-solution queries."
            ),
            source_url="system://market-context-plan",
            agent=self.name,
            confidence=0.35,
        )
        lead.evidence.append(evidence)

        summary = (
            "needs_enrichment: competitor and local alternative checks are planned "
            "but not yet executed by a live market-search provider."
        )
        return MarketContext(
            campaign_id=campaign.id,
            lead_id=lead.id,
            summary=summary,
            local_competitor_queries=queries,
            gap_hypotheses=gap_hypotheses,
            evidence_ids=[evidence.id],
            status="needs_enrichment",
        )

    def _competitor_queries(
        self,
        campaign: CampaignContext,
        spec: CampaignSpec,
        lead: LeadMemory,
        industry: str,
        locality: str,
    ) -> list[str]:
        place = locality or " ".join(campaign.countries)
        base = f"{industry} {place}".strip()
        queries = [
            f"{base} competitors",
            f"{base} alternatives {campaign.offer}",
            f"{base} customer contact workflow",
        ]
        queries.extend(spec.search_queries[:2])
        return self._dedupe(queries)[:6]

    def _gap_hypotheses(self, spec: CampaignSpec, assessment: LeadAssessment) -> list[str]:
        gaps = []
        if not assessment.buyer_signals:
            gaps.append("pain needs stronger public evidence")
        if assessment.solution.status.value == "strong_solution":
            gaps.append("mature existing tooling may reduce urgency")
        if assessment.component_scores.get("contactability", 0) == 0:
            gaps.append("contact path needs manual verification")
        gaps.extend(f"compare against competitors for {pain}" for pain in spec.pain_hypotheses[:2])
        return self._dedupe(gaps)[:6]

    def _dedupe(self, values: list[str]) -> list[str]:
        result = []
        for value in values:
            if value and value not in result:
                result.append(value)
        return result
