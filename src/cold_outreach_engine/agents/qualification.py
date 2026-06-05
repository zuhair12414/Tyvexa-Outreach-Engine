from __future__ import annotations

import re

from cold_outreach_engine.models import (
    BuyerSignal,
    CampaignContext,
    CampaignSpec,
    Evidence,
    EvidencePack,
    LeadAssessment,
    LeadMemory,
    LeadScore,
    LeadStatus,
    SolutionAssessment,
    SolutionStatus,
)


class LeadQualificationAgent:
    name = "qualification_agent"
    rubric_version = "dynamic_assessment_v1"

    STRONG_SOLUTION_MARKERS = {
        "intercom": "customer messaging platform",
        "hubspot": "CRM/contact automation",
        "zendesk": "support desk",
        "salesforce": "CRM platform",
        "freshdesk": "support desk",
    }

    WEAK_SOLUTION_MARKERS = {
        "calendly": "scheduler",
        "whatsapp": "manual messaging",
        "contact form": "web contact form",
        "booking": "booking or intake flow",
        "chatbot": "basic chatbot",
        "live chat": "live chat",
        "ivr": "phone menu or routing",
    }

    SUSPICIOUS_TERMS = ["shady", "scam", "fake", "unclear ownership"]

    NON_BUYER_MARKERS = [
        "government",
        "municipality",
        "public authority",
        "wikipedia",
        "news article",
        "directory of",
        "list of",
        "best companies",
        "marketplace",
        "job posting",
        "training course",
        "university",
        "museum",
    ]

    def run(
        self,
        campaign: CampaignContext,
        spec: CampaignSpec,
        lead: LeadMemory,
        evidence_pack: EvidencePack,
    ) -> tuple[LeadAssessment, LeadScore]:
        buyer_signals = self._buyer_signals(spec, lead, evidence_pack)
        solution = self._solution_assessment(lead, evidence_pack)
        component_scores = {
            "icp_fit": self._icp_fit(spec, lead),
            "public_evidence": self._public_evidence_score(lead, evidence_pack),
            "contactability": 15 if evidence_pack.contact_markers else 0,
            "pain_signal": min(25, sum(signal.strength for signal in buyer_signals) * 8),
            "solution_gap": self._solution_gap_score(solution.status),
            "trust": self._trust_score(campaign, lead),
        }
        raw_total = sum(component_scores.values())
        total = self._apply_solution_caps(raw_total, solution.status)
        if total != raw_total:
            component_scores["strong_solution_cap"] = total - raw_total
        status, reject_reason = self._status_for(
            lead, evidence_pack, total, component_scores, solution.status
        )

        assessment = LeadAssessment(
            campaign_id=campaign.id,
            lead_id=lead.id,
            status=status,
            score=total,
            reasons=[f"{name}: {value}" for name, value in component_scores.items()],
            reject_reason=reject_reason,
            buyer_signals=buyer_signals,
            solution=solution,
            component_scores=component_scores,
            evidence_ids=evidence_pack.evidence_ids,
            rubric_version=self.rubric_version,
        )
        score = LeadScore(
            lead_id=lead.id,
            status=status,
            total=total,
            reasons=assessment.reasons,
            reject_reason=reject_reason,
            solution_status=solution.status,
            component_scores=component_scores,
            rubric_version=self.rubric_version,
        )
        return assessment, score

    def _buyer_signals(
        self, spec: CampaignSpec, lead: LeadMemory, evidence_pack: EvidencePack
    ) -> list[BuyerSignal]:
        signals: list[BuyerSignal] = []
        source_url = lead.website or self._first_public_source(lead)
        for pain in spec.pain_hypotheses:
            terms = self._terms_for(pain)
            matched = [
                term
                for term in terms
                if term in evidence_pack.pain_markers or self._term_in_facts(term, evidence_pack)
            ]
            if not matched:
                continue
            evidence = Evidence(
                claim=(
                    f"Observed campaign pain hypothesis '{pain}' through public markers: "
                    f"{', '.join(matched[:4])}."
                ),
                source_url=source_url,
                agent=self.name,
                confidence=0.65,
            )
            lead.evidence.append(evidence)
            signals.append(
                BuyerSignal(
                    lead_id=lead.id,
                    name=pain,
                    strength=min(3, max(1, len(set(matched)))),
                    reason=evidence.claim,
                    evidence_ids=[evidence.id],
                )
            )
        return signals[:5]

    def _solution_assessment(
        self, lead: LeadMemory, evidence_pack: EvidencePack
    ) -> SolutionAssessment:
        detected = evidence_pack.solution_markers
        strong = [marker for marker in detected if marker in self.STRONG_SOLUTION_MARKERS]
        weak = [marker for marker in detected if marker in self.WEAK_SOLUTION_MARKERS]

        if strong:
            status = SolutionStatus.STRONG_SOLUTION
            implication = "Visible mature tooling; deprioritize unless the campaign pain evidence is strong."
        elif weak:
            status = SolutionStatus.WEAK_SOLUTION
            implication = "Visible partial or manual intake tooling; qualify if the campaign pain is also evidenced."
        elif lead.website:
            status = SolutionStatus.UNKNOWN
            implication = "No public solution marker detected; classify as unknown, not confirmed no-solution."
        else:
            status = SolutionStatus.UNKNOWN
            implication = "No public verification path for existing solutions."

        evidence = Evidence(
            claim=f"Detected public solution markers: {', '.join(detected) or 'none visible'}",
            source_url=lead.website or self._first_public_source(lead),
            agent=self.name,
            confidence=0.6 if detected else 0.35,
        )
        lead.evidence.append(evidence)
        solution_types = [
            self.STRONG_SOLUTION_MARKERS.get(marker)
            or self.WEAK_SOLUTION_MARKERS.get(marker)
            or marker
            for marker in detected
        ]
        return SolutionAssessment(
            lead_id=lead.id,
            status=status,
            solution_type=", ".join(solution_types) if solution_types else "unknown",
            detected_tools=detected,
            outreach_implication=implication,
            evidence_ids=[evidence.id],
        )

    def _icp_fit(self, spec: CampaignSpec, lead: LeadMemory) -> int:
        text = f"{lead.company_name} {lead.industry or ''} {' '.join(lead.facts[:3])}".lower()
        if any(industry.lower() in text for industry in spec.target_industries):
            return 20
        return 10 if lead.industry or lead.facts else 0

    def _public_evidence_score(self, lead: LeadMemory, evidence_pack: EvidencePack) -> int:
        if lead.website and evidence_pack.page_urls:
            return 20
        if lead.website or evidence_pack.evidence_ids:
            return 12
        return 0

    def _solution_gap_score(self, status: SolutionStatus) -> int:
        if status in {SolutionStatus.UNKNOWN, SolutionStatus.NO_SOLUTION}:
            return 10
        if status == SolutionStatus.WEAK_SOLUTION:
            return 6
        return 1

    def _apply_solution_caps(self, total: int, status: SolutionStatus) -> int:
        if status == SolutionStatus.STRONG_SOLUTION:
            return min(total, 65)
        return total

    def _trust_score(self, campaign: CampaignContext, lead: LeadMemory) -> int:
        text = " ".join(lead.facts).lower()
        if any(term in text for term in self.SUSPICIOUS_TERMS):
            return -20
        if any("shady" in rule.lower() for rule in campaign.reject_rules) and "shady" in text:
            return -20
        return 10

    def _status_for(
        self,
        lead: LeadMemory,
        evidence_pack: EvidencePack,
        total: int,
        component_scores: dict[str, int],
        solution_status: SolutionStatus,
    ) -> tuple[LeadStatus, str | None]:
        if not lead.website:
            return LeadStatus.REJECTED, "Rejected by rubric: no website/public verification path."

        disqualifier = self._hard_disqualifier(lead)
        if disqualifier:
            return LeadStatus.REJECTED, disqualifier

        if component_scores["trust"] < 0:
            return LeadStatus.REJECTED, "Rejected by rubric: trust or legitimacy concern."

        if solution_status == SolutionStatus.STRONG_SOLUTION and total >= 50:
            return LeadStatus.MANUAL_REVIEW, None
        if total >= 70:
            return LeadStatus.QUALIFIED, None
        if total >= 50:
            return LeadStatus.MANUAL_REVIEW, None
        if total >= 35:
            return LeadStatus.NEEDS_INPUT, None
        return LeadStatus.REJECTED, "Rejected by rubric: insufficient buyer and evidence signals."

    def _hard_disqualifier(self, lead: LeadMemory) -> str | None:
        name = lead.company_name.strip().lower()
        facts = " ".join(lead.facts).lower()
        website = (lead.website or "").lower()
        generic_names = {"contact", "contact us", "about us", "services", "home", "menu"}
        if name in generic_names:
            return "Rejected by rubric: generic page title, not a clear company lead."
        if any(marker in facts for marker in self.NON_BUYER_MARKERS):
            return "Rejected by rubric: page appears to be a non-buyer source."
        if any(marker in website for marker in ["wikipedia.", "facebook.com", "linkedin.com"]):
            return "Rejected by rubric: source domain is not a public company website."
        return None

    def _terms_for(self, phrase: str) -> list[str]:
        words = [
            word
            for word in re.split(r"[^a-z0-9]+", phrase.lower())
            if len(word) > 3 and word not in {"manual", "customer", "workflow"}
        ]
        return [phrase.lower(), *words]

    def _term_in_facts(self, term: str, evidence_pack: EvidencePack) -> bool:
        return term.lower() in " ".join(evidence_pack.facts).lower()

    def _first_public_source(self, lead: LeadMemory) -> str:
        for evidence in lead.evidence:
            if not evidence.source_url.startswith("system://"):
                return evidence.source_url
        return "system://lead-memory"
