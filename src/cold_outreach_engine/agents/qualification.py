from __future__ import annotations

from cold_outreach_engine.models import CampaignContext, Evidence, LeadMemory, LeadScore, LeadStatus
from cold_outreach_engine.providers.base import CrawlProvider


class LeadQualificationAgent:
    name = "lead_qualification_agent"

    def __init__(self, crawl_provider: CrawlProvider) -> None:
        self.crawl_provider = crawl_provider

    def run(self, campaign: CampaignContext, lead: LeadMemory) -> tuple[LeadMemory, LeadScore]:
        pages = self.crawl_provider.crawl_company(
            type("Candidate", (), {"website": lead.website, "name": lead.company_name})()
        )

        component_scores = {
            "has_website": 20 if lead.website else 0,
            "public_info": 20 if lead.facts or pages else 0,
            "contactability": 15 if any("phone" in page.text.lower() for page in pages) else 0,
            "pain_signal": 20 if self._has_pain_signal(campaign, lead, pages) else 0,
            "trust": 15 if not self._looks_shady(campaign, lead) else -30,
        }
        total = sum(component_scores.values())

        for page in pages:
            lead.evidence.append(
                Evidence(
                    claim=f"Public website page was available for qualification: {page.title}",
                    source_url=page.url,
                    agent=self.name,
                    confidence=0.75,
                )
            )
            lead.facts.append(page.text[:400])

        if not lead.website:
            status = LeadStatus.REJECTED
            reject_reason = "No website available for public verification."
        elif total >= 60:
            status = LeadStatus.MANUAL_REVIEW
            reject_reason = None
        elif total >= 35:
            status = LeadStatus.NEEDS_INPUT
            reject_reason = None
        else:
            status = LeadStatus.REJECTED
            reject_reason = "Insufficient public signals for this campaign."

        score = LeadScore(
            lead_id=lead.id,
            status=status,
            total=total,
            reasons=self._reasons(component_scores),
            reject_reason=reject_reason,
            component_scores=component_scores,
        )
        return lead, score

    def _has_pain_signal(self, campaign: CampaignContext, lead: LeadMemory, pages: list) -> bool:
        text = " ".join(lead.facts + [page.text for page in pages]).lower()
        signal_terms = [signal.lower() for signal in campaign.pain_signals]
        default_voice_terms = ["phone", "call", "reservation", "support", "slow response", "whatsapp"]
        return any(term in text for term in signal_terms + default_voice_terms)

    def _looks_shady(self, campaign: CampaignContext, lead: LeadMemory) -> bool:
        text = " ".join(lead.facts).lower()
        return any(rule.lower() in text for rule in campaign.reject_rules if "shady" in rule.lower())

    def _reasons(self, scores: dict[str, int]) -> list[str]:
        return [f"{name}: {value}" for name, value in scores.items()]

