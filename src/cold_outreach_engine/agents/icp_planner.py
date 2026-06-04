from __future__ import annotations

import re

from cold_outreach_engine.models import CampaignContext


class IcpPlannerAgent:
    name = "icp_planner_agent"

    COUNTRY_ALIASES = {
        "finland": "Finland",
        "uae": "UAE",
        "united arab emirates": "UAE",
        "saudi": "Saudi Arabia",
        "saudi arabia": "Saudi Arabia",
        "qatar": "Qatar",
        "germany": "Germany",
        "uk": "United Kingdom",
        "united kingdom": "United Kingdom",
        "france": "France",
        "spain": "Spain",
        "netherlands": "Netherlands",
    }

    INDUSTRY_ALIASES = {
        "restaurant": "restaurants",
        "restaurants": "restaurants",
        "bpo": "BPO",
        "call center": "BPO",
        "customer service": "customer service",
        "insurance": "insurance",
        "clinic": "clinics",
        "salon": "salons",
    }

    def plan(self, prompt: str) -> CampaignContext:
        normalized = prompt.lower()
        countries = self._extract_aliases(normalized, self.COUNTRY_ALIASES)
        industries = self._extract_aliases(normalized, self.INDUSTRY_ALIASES)
        offer = self._extract_offer(normalized)

        return CampaignContext(
            prompt=prompt,
            offer=offer,
            countries=countries or ["Finland"],
            industries=industries or ["restaurants"],
            ideal_company=(
                "publicly verifiable business with website, reviews/social proof, "
                "clear service offering, and customer contact path"
            ),
            pain_signals=self._pain_signals_for(offer, industries),
            reject_rules=[
                "no website and no public identity",
                "no clear service offering",
                "shady or unclear business",
                "no usable contact path",
            ],
        )

    def _extract_aliases(self, text: str, aliases: dict[str, str]) -> list[str]:
        found: list[str] = []
        for alias, value in aliases.items():
            if re.search(rf"\b{re.escape(alias)}\b", text) and value not in found:
                found.append(value)
        return found

    def _extract_offer(self, text: str) -> str:
        if "voice ai" in text or "voice-ai" in text:
            return "voice AI for missed calls, reservations, and customer support"
        return "AI automation services"

    def _pain_signals_for(self, offer: str, industries: list[str]) -> list[str]:
        signals = [
            "phone-heavy workflow",
            "missed calls",
            "slow response",
            "weak reachout methods",
            "manual contact flow",
        ]
        if "restaurants" in industries or "restaurant" in " ".join(industries).lower():
            signals.extend(["reservations", "booking friction", "after-hours calls"])
        if "bpo" in " ".join(industries).lower() or "customer service" in industries:
            signals.extend(["support volume", "call overflow", "customer service burden"])
        return signals

