from __future__ import annotations

from cold_outreach_engine.models import (
    BuyerSignal,
    CampaignContext,
    LeadMemory,
    LeadScore,
    LeadStatus,
    SolutionAssessment,
    SolutionStatus,
)


class ScoringAgent:
    name = "scoring_agent"
    rubric_version = "v1"

    def run(
        self,
        campaign: CampaignContext,
        lead: LeadMemory,
        buyer_signals: list[BuyerSignal],
        solution: SolutionAssessment,
        competitor_gap: str,
    ) -> LeadScore:
        component_scores = {
            "icp_fit": self._icp_fit(campaign, lead),
            "contactability": 2 if lead.website else 0,
            "buyer_signal": min(3, sum(signal.strength for signal in buyer_signals)),
            "solution_weakness": self._solution_score(solution.status),
            "competitor_pressure": 1 if "placeholder" not in competitor_gap else 0,
            "evidence_quality": min(2, len([e for e in lead.evidence if not e.source_url.startswith("system://")])),
            "trust_penalty": self._trust_penalty(campaign, lead),
        }
        total = sum(component_scores.values())

        reject_reason = None
        if not lead.website:
            status = LeadStatus.REJECTED
            reject_reason = "Rejected by rubric: no website/public verification path."
        elif component_scores["trust_penalty"] < 0:
            status = LeadStatus.REJECTED
            reject_reason = "Rejected by rubric: trust or legitimacy concern."
        elif total >= 8:
            status = LeadStatus.QUALIFIED
        elif total >= 5:
            status = LeadStatus.MANUAL_REVIEW
        elif total >= 3:
            status = LeadStatus.NEEDS_INPUT
        else:
            status = LeadStatus.REJECTED
            reject_reason = "Rejected by rubric: insufficient buyer and evidence signals."

        return LeadScore(
            lead_id=lead.id,
            status=status,
            total=total,
            reasons=[f"{name}: {value}" for name, value in component_scores.items()],
            reject_reason=reject_reason,
            solution_status=solution.status,
            component_scores=component_scores,
            rubric_version=self.rubric_version,
        )

    def _icp_fit(self, campaign: CampaignContext, lead: LeadMemory) -> int:
        industry = (lead.industry or "").lower()
        if any(target.lower() in industry or industry in target.lower() for target in campaign.industries):
            return 2
        return 1 if industry else 0

    def _solution_score(self, status: SolutionStatus) -> int:
        if status in {SolutionStatus.NO_SOLUTION, SolutionStatus.UNKNOWN}:
            return 2
        if status == SolutionStatus.WEAK_SOLUTION:
            return 1
        return 0

    def _trust_penalty(self, campaign: CampaignContext, lead: LeadMemory) -> int:
        text = " ".join(lead.facts).lower()
        suspicious_terms = ["shady", "unclear", "scam", "fake"]
        if any(term in text for term in suspicious_terms):
            return -3
        return 0

