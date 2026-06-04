from __future__ import annotations

from cold_outreach_engine.models import BuyerSignal, CampaignContext, Evidence, LeadMemory


class BuyerSignalAgent:
    name = "buyer_signal_agent"

    SIGNAL_TERMS = {
        "phone_dependency": ["phone", "call", "calls", "callback"],
        "slow_response": ["slow response", "difficulty reaching", "never answered", "no answer"],
        "reservation_or_booking_friction": ["reservation", "booking", "book", "after-hours"],
        "manual_contact_flow": ["whatsapp", "contact form", "manual contact"],
        "support_volume": ["support", "customer service", "helpdesk", "call overflow"],
    }

    def run(self, campaign: CampaignContext, lead: LeadMemory) -> list[BuyerSignal]:
        text = " ".join(lead.facts).lower()
        primary_evidence = self._best_evidence(lead)
        signals: list[BuyerSignal] = []

        for signal_name, terms in self.SIGNAL_TERMS.items():
            matched_terms = [term for term in terms if term in text]
            if not matched_terms:
                continue
            evidence = Evidence(
                claim=(
                    f"Detected buyer signal '{signal_name}' from public lead facts: "
                    f"{', '.join(matched_terms[:3])}."
                ),
                source_url=primary_evidence.source_url if primary_evidence else "system://lead-memory",
                agent=self.name,
                confidence=0.65,
            )
            lead.evidence.append(evidence)
            signals.append(
                BuyerSignal(
                    lead_id=lead.id,
                    name=signal_name,
                    strength=self._strength_for(signal_name, matched_terms, campaign),
                    reason=evidence.claim,
                    evidence_ids=[evidence.id],
                )
            )

        return signals

    def _best_evidence(self, lead: LeadMemory) -> Evidence | None:
        public = [e for e in lead.evidence if not e.source_url.startswith("system://")]
        if public:
            return public[-1]
        return lead.evidence[-1] if lead.evidence else None

    def _strength_for(
        self, signal_name: str, matched_terms: list[str], campaign: CampaignContext
    ) -> int:
        strength = min(3, len(set(matched_terms)))
        if "voice" in campaign.offer.lower() and signal_name in {
            "phone_dependency",
            "slow_response",
            "reservation_or_booking_friction",
        }:
            strength += 1
        return min(3, max(1, strength))

