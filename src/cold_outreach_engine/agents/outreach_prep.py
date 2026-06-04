from __future__ import annotations

from cold_outreach_engine.models import (
    BuyerSignal,
    CampaignContext,
    DossierClaim,
    LeadDossier,
    LeadMemory,
    LeadScore,
    LeadStatus,
    SolutionAssessment,
)


class OutreachPrepAgent:
    name = "outreach_prep_agent"

    def run(
        self,
        campaign: CampaignContext,
        lead: LeadMemory,
        score: LeadScore,
        competitor_gap: str,
        solution_assessment: SolutionAssessment,
        buyer_signals: list[BuyerSignal],
    ) -> LeadDossier:
        persona = self._persona_for(lead.industry)
        status = score.status

        claims = self._claims_for(lead, buyer_signals, solution_assessment)
        evidence_summary = [
            f"{claim.text} [evidence: {', '.join(claim.evidence_ids) or 'unknown'}]"
            for claim in claims
        ]
        flow_label = self._flow_label(solution_assessment)
        if score.status == LeadStatus.REJECTED:
            opening = f"No outreach recommended. {score.reject_reason or 'Lead failed qualification rubric.'}"
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
            score=score.total,
            why_this_lead="; ".join(score.reasons),
            evidence_summary=evidence_summary,
            competitor_gap=competitor_gap,
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

    def _persona_for(self, industry: str | None) -> str:
        if not industry:
            return "Founder, owner, operations manager, or customer service manager"
        lower = industry.lower()
        if "restaurant" in lower:
            return (
                "Single location: owner or general manager; group: operations manager, "
                "COO, or reservations manager"
            )
        if "bpo" in lower or "customer" in lower:
            return "VP operations, head of customer support, contact center manager, or CTO"
        if "insurance" in lower:
            return "Operations manager, claims manager, or customer experience lead"
        return "Founder, owner, manager, or operations lead"
