from __future__ import annotations

import re

from cold_outreach_engine.models import CampaignContext, CampaignSpec


class CampaignStrategyAgent:
    name = "campaign_strategy_agent"

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
        "middle east": "Middle East",
        "eu": "European Union",
        "europe": "Europe",
    }

    CAPABILITY_PAIN_PRIORS = {
        "voice": [
            "missed inbound calls",
            "phone dependency",
            "manual call handling",
            "slow callback or response loops",
            "after-hours coverage gaps",
            "manual booking, appointment, or inquiry intake",
        ],
        "phone": [
            "missed inbound calls",
            "manual phone intake",
            "slow callback or response loops",
        ],
        "support": [
            "support volume",
            "slow customer response",
            "manual triage",
            "repeat inquiry handling",
        ],
        "sales": [
            "slow lead response",
            "manual qualification",
            "inconsistent follow-up",
        ],
        "automation": [
            "manual workflow burden",
            "repetitive operations work",
            "slow handoffs between tools or teams",
        ],
    }

    SOURCE_DESCRIPTIONS = {
        "google_places": "location-based company discovery",
        "firecrawl_search": "broad public web discovery",
        "brave_search": "broad search discovery",
        "company_websites": "first-party evidence extraction",
        "review_sites": "customer pain and reputation evidence",
        "company_directories": "category and legitimacy cross-checks",
    }

    def plan(self, prompt: str) -> tuple[CampaignContext, CampaignSpec]:
        campaign = self.create_campaign(prompt)
        return campaign, self.build_spec(campaign)

    def create_campaign(self, prompt: str) -> CampaignContext:
        normalized = self._normalize(prompt)
        countries = self._extract_countries(normalized)
        industries = self._extract_industries(prompt)
        offer = self._extract_offer(prompt)
        pain_signals = self._pain_hypotheses(offer, prompt)

        return CampaignContext(
            prompt=prompt,
            offer=offer,
            countries=countries or ["unspecified"],
            industries=industries or ["unspecified target businesses"],
            ideal_company=(
                "publicly verifiable business with a clear service offering, "
                "credible web presence, and reachable decision maker"
            ),
            pain_signals=pain_signals,
            reject_rules=[
                "no public verification path",
                "no clear service offering",
                "directory, platform, media, government, or educational page instead of a buyer",
                "shady or unclear business identity",
                "no usable contact path",
            ],
        )

    def build_spec(self, campaign: CampaignContext) -> CampaignSpec:
        source_priorities = self._source_priorities(campaign)
        search_queries = self._search_queries(campaign)
        buyer_personas = self._buyer_personas(campaign)
        return CampaignSpec(
            campaign_id=campaign.id,
            target_industries=campaign.industries,
            countries=campaign.countries,
            offer=campaign.offer,
            pain_hypotheses=campaign.pain_signals,
            good_lead_traits=[
                "clear company identity",
                "public website or authoritative business profile",
                "visible service offering",
                "observable customer-contact workflow",
                "credible activity or growth signal",
            ],
            reject_rules=campaign.reject_rules,
            source_priorities=source_priorities,
            search_queries=search_queries,
            evidence_requirements=[
                "source URL for discovery",
                "website or authoritative public profile",
                "company/service evidence",
                "contact-path evidence",
                "pain or workflow evidence before confident qualification",
            ],
            buyer_personas=buyer_personas,
            scoring_rubric={
                "icp_fit": 20,
                "public_evidence": 20,
                "contactability": 15,
                "pain_signal": 25,
                "solution_gap": 10,
                "trust": 10,
            },
            clarification_triggers=[
                "missing country or target segment",
                "public evidence is thin but the business appears relevant",
                "pain signal is inferred from workflow rather than directly observed",
                "lead seems to use a mature existing solution",
            ],
            confidence_notes=[
                "Spec is generated per campaign; it is not a permanent industry profile.",
                "Qualification should prefer explicit public evidence over assumptions.",
            ],
        )

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", text.lower()).strip()

    def _extract_countries(self, text: str) -> list[str]:
        found: list[str] = []
        for alias, value in self.COUNTRY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", text) and value not in found:
                found.append(value)
        return found

    def _extract_industries(self, prompt: str) -> list[str]:
        candidates: list[str] = []
        patterns = [
            r"\bfor\s+(.+?)\s+(?:businesses|companies|firms|agencies|operators|providers)\b",
            r"\b(?:target|targeting)\s+(.+?)(?:\s+in\b|\s+looking\b|\s+with\b|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                candidates.extend(self._split_phrase(match.group(1)))

        if not candidates:
            match = re.search(r"\b(?:industry|industries|verticals?)\s*:\s*(.+)", prompt, flags=re.IGNORECASE)
            if match:
                candidates.extend(self._split_phrase(match.group(1)))

        cleaned = []
        for candidate in candidates:
            value = self._clean_segment(candidate)
            if value and value not in cleaned:
                cleaned.append(value)
        return cleaned[:6]

    def _split_phrase(self, phrase: str) -> list[str]:
        phrase = re.split(r"\b(?:looking for|needing|that need|with pain|offer)\b", phrase, maxsplit=1, flags=re.IGNORECASE)[0]
        return [
            chunk.strip()
            for chunk in re.split(r",|\band\b|/|\|", phrase, flags=re.IGNORECASE)
            if chunk.strip()
        ]

    def _clean_segment(self, value: str) -> str:
        value = re.sub(r"\b(leads?|businesses?|companies?|firms?|providers?)\b", "", value, flags=re.IGNORECASE)
        value = re.sub(r"[^a-zA-Z0-9 &+-]+", " ", value)
        return re.sub(r"\s+", " ", value).strip().lower()

    def _extract_offer(self, prompt: str) -> str:
        for pattern in [
            r"\blooking for\s+(.+)$",
            r"\boffer\s*:\s*(.+)$",
            r"\bneed(?:s|ing)?\s+(.+)$",
        ]:
            match = re.search(pattern, prompt, flags=re.IGNORECASE)
            if match:
                return self._clean_offer(match.group(1))
        if re.search(r"\bvoice\s*ai\b", prompt, flags=re.IGNORECASE):
            return "voice AI capabilities"
        return "AI automation services"

    def _clean_offer(self, value: str) -> str:
        value = re.split(r"\b(?:countries|target industries|reject if|output amount)\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
        value = value.strip(" .,:;")
        return value or "AI automation services"

    def _pain_hypotheses(self, offer: str, prompt: str) -> list[str]:
        text = f"{offer} {prompt}".lower()
        signals: list[str] = []
        for capability, priors in self.CAPABILITY_PAIN_PRIORS.items():
            if capability in text:
                signals.extend(prior for prior in priors if prior not in signals)

        prompt_pains = re.findall(r"\b(?:pain|problems?|signals?)\s*:\s*([^.;\n]+)", prompt, flags=re.IGNORECASE)
        for phrase in prompt_pains:
            for item in self._split_phrase(phrase):
                cleaned = self._clean_segment(item)
                if cleaned and cleaned not in signals:
                    signals.append(cleaned)

        if not signals:
            signals = [
                "manual workflow burden",
                "slow response",
                "weak customer contact flow",
            ]
        return signals[:10]

    def _source_priorities(self, campaign: CampaignContext) -> list[str]:
        prompt = campaign.prompt.lower()
        local_likely = bool(
            re.search(r"\b(local|nearby|city|location|branch|branches|storefront)\b", prompt)
            or re.search(r"\bfor\b.+\b(businesses|storefronts|shops|branches)\b", prompt)
        )
        sources = ["firecrawl_search", "brave_search", "company_websites", "company_directories"]
        if local_likely:
            sources.insert(0, "google_places")
            sources.insert(2, "review_sites")
        return sources

    def _search_queries(self, campaign: CampaignContext) -> list[str]:
        queries: list[str] = []
        countries = campaign.countries or ["unspecified"]
        industries = campaign.industries or ["target businesses"]
        pain_terms = campaign.pain_signals[:3]
        for country in countries:
            for industry in industries:
                base = f"{industry} {country}".strip()
                queries.append(f"{base} {campaign.offer}")
                queries.append(f"{base} official website contact")
                for pain in pain_terms[:2]:
                    queries.append(f"{base} {pain}")
        return self._dedupe(queries)[:12]

    def _buyer_personas(self, campaign: CampaignContext) -> list[str]:
        text = f"{campaign.offer} {' '.join(campaign.industries)}".lower()
        personas = ["founder", "owner", "operations manager"]
        if any(term in text for term in ["support", "customer", "call center", "bpo"]):
            personas.extend(["head of customer support", "contact center manager", "customer experience lead"])
        if any(term in text for term in ["technical", "api", "automation", "ai"]):
            personas.extend(["CTO", "automation lead"])
        return self._dedupe(personas)[:8]

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = re.sub(r"\s+", " ", value).strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result
