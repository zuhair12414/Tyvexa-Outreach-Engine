from __future__ import annotations

from cold_outreach_engine.models import (
    BuyerSignal,
    CampaignContext,
    CampaignSpec,
    DossierClaim,
    LeadAssessment,
    LeadDossier,
    LeadMemory,
    LeadStatus,
    MarketContext,
    SolutionAssessment,
)


class OutreachPrepAgent:
    name = "outreach_prep_agent"

    def run(
        self,
        campaign: CampaignContext,
        spec: CampaignSpec,
        lead: LeadMemory,
        assessment: LeadAssessment,
        market_context: MarketContext,
    ) -> LeadDossier:
        persona = self._persona_for(spec, lead.industry)
        status = assessment.status
        solution_assessment = assessment.solution
        buyer_signals = assessment.buyer_signals

        claims = self._claims_for(lead, buyer_signals, solution_assessment)
        evidence_summary = [
            f"{claim.text} [evidence: {', '.join(claim.evidence_ids) or 'unknown'}]"
            for claim in claims
        ]
        flow_label = self._flow_label(solution_assessment)
        if assessment.status == LeadStatus.REJECTED:
            opening = f"No outreach recommended. {assessment.reject_reason or 'Lead failed qualification rubric.'}"
        else:
            opening = (
                f"Hi, noticed {lead.company_name} may still rely on {flow_label}. "
                f"We help teams with {campaign.offer}. Worth comparing notes?"
            )

        return LeadDossier(
            campaign_id=campaign.id,
            lead_id=lead.id,
            company_name=lead.company_name,
            status=status,
            score=assessment.score,
            why_this_lead="; ".join(assessment.reasons),
            evidence_summary=evidence_summary,
            competitor_gap=market_context.summary,
            solution_assessment=(
                f"{solution_assessment.status.value}: {solution_assessment.outreach_implication}"
            ),
            linkedin_persona=persona,
            linkedin_search_hint=f'Search LinkedIn manually for "{persona}" at "{lead.company_name}".',
            manual_opening_message=opening,
            claims=claims,
        )

    def _claims_for(
        self,
        lead: LeadMemory,
        buyer_signals: list[BuyerSignal],
        solution: SolutionAssessment,
    ) -> list[DossierClaim]:
        claims: list[DossierClaim] = []
        for signal in buyer_signals[:3]:
            claims.append(
                DossierClaim(
                    text=signal.reason,
                    evidence_ids=signal.evidence_ids,
                    confidence=min(0.8, 0.45 + (signal.strength * 0.15)),
                )
            )
        claims.append(
            DossierClaim(
                text=solution.outreach_implication,
                evidence_ids=solution.evidence_ids,
                confidence=0.55,
            )
        )
        if not claims:
            claims.append(
                DossierClaim(
                    text="Unknown - needs verification before outreach.",
                    evidence_ids=[],
                    confidence=0.0,
                )
            )
        return claims

    def _flow_label(self, solution: SolutionAssessment) -> str:
        if solution.solution_type == "unknown":
            return "a publicly unclear customer intake flow"
        return solution.solution_type

    def _persona_for(self, spec: CampaignSpec, industry: str | None) -> str:
        personas = spec.buyer_personas or ["founder", "owner", "operations manager"]
        if industry:
            return f"{', '.join(personas[:4])} for {industry}"
        return ", ".join(personas[:4])
