from __future__ import annotations

import re
from typing import Any

from cold_outreach_engine.models import CampaignContext, CampaignSpec
from cold_outreach_engine.providers.base import LlmProvider


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

    def __init__(self, llm_provider: LlmProvider | None = None) -> None:
        self.llm_provider = llm_provider

    def plan(self, prompt: str) -> tuple[CampaignContext, CampaignSpec]:
        if self.llm_provider:
            try:
                raw_plan = self.llm_provider.classify(
                    "campaign_strategy",
                    {
                        "prompt": prompt,
                        "available_sources": self.SOURCE_DESCRIPTIONS,
                        "required_behavior": [
                            "infer geography, including city and country when present",
                            "infer target industries and buyer segment",
                            "infer offer and solution gap from negative constraints",
                            "generate search queries that include city/locality when present",
                            "do not produce leads or unsupported factual claims",
                        ],
                    },
                )
                return self._plan_from_ai(prompt, raw_plan)
            except Exception as exc:
                campaign = self.create_campaign(prompt)
                spec = self.build_spec(campaign)
                spec.confidence_notes.append(
                    f"AI strategy unavailable; used heuristic fallback. Error: {type(exc).__name__}."
                )
                return campaign, spec

        campaign = self.create_campaign(prompt)
        spec = self.build_spec(campaign)
        spec.confidence_notes.append("No LLM provider configured; set OPENAI_API_KEY for AI strategy.")
        return campaign, spec

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
                "Spec is generated by deterministic fallback; use OPENAI_API_KEY for AI planning.",
                "Qualification should prefer explicit public evidence over assumptions.",
            ],
            target_locations=campaign.countries,
            solution_gaps=[],
            strategy_source="heuristic_fallback",
        )

    def _plan_from_ai(self, prompt: str, raw: dict[str, Any]) -> tuple[CampaignContext, CampaignSpec]:
        countries = self._list(raw.get("countries"))
        target_locations = self._list(raw.get("target_locations"))
        industries = self._list(raw.get("target_industries")) or ["unspecified target businesses"]
        offer = self._text(raw.get("offer")) or "AI automation services"
        pain_hypotheses = self._list(raw.get("pain_hypotheses")) or [
            "manual workflow burden",
            "slow response",
            "weak customer contact flow",
        ]
        solution_gaps = self._list(raw.get("solution_gaps"))
        reject_rules = self._list(raw.get("reject_rules")) or [
            "no public verification path",
            "no clear service offering",
            "directory, platform, media, government, or educational page instead of a buyer",
            "shady or unclear business identity",
            "no usable contact path",
        ]
        market_scope = target_locations or countries or ["unspecified"]

        campaign = CampaignContext(
            prompt=prompt,
            offer=offer,
            countries=market_scope,
            industries=industries,
            ideal_company="; ".join(self._list(raw.get("good_lead_traits"))[:4])
            or "publicly verifiable business with credible web presence",
            pain_signals=self._dedupe([*pain_hypotheses, *solution_gaps])[:12],
            reject_rules=reject_rules,
        )

        source_priorities = self._valid_sources(raw.get("source_priorities")) or self._source_priorities(campaign)
        search_queries = self._list(raw.get("search_queries")) or self._search_queries(campaign)
        scoring_rubric = self._scoring_rubric(raw.get("scoring_rubric"))
        confidence_notes = self._list(raw.get("confidence_notes"))
        confidence_notes.insert(
            0,
            "Campaign operating spec generated by AI API, then normalized by local validation.",
        )

        spec = CampaignSpec(
            campaign_id=campaign.id,
            target_industries=industries,
            countries=countries or market_scope,
            offer=offer,
            pain_hypotheses=pain_hypotheses,
            good_lead_traits=self._list(raw.get("good_lead_traits")) or [
                "clear company identity",
                "public website or authoritative business profile",
                "visible service offering",
                "observable customer-contact workflow",
            ],
            reject_rules=reject_rules,
            source_priorities=source_priorities,
            search_queries=search_queries[:12],
            evidence_requirements=self._list(raw.get("evidence_requirements")) or [
                "source URL for discovery",
                "website or authoritative public profile",
                "company/service evidence",
                "contact-path evidence",
                "solution-gap evidence before confident qualification",
            ],
            buyer_personas=self._list(raw.get("buyer_personas")) or self._buyer_personas(campaign),
            scoring_rubric=scoring_rubric,
            clarification_triggers=self._list(raw.get("clarification_triggers")) or [
                "campaign target is underspecified",
                "solution gap is inferred but not evidenced",
                "public evidence is thin but the business appears relevant",
            ],
            target_locations=target_locations,
            solution_gaps=solution_gaps,
            strategy_source="ai_api",
            strategy_model=self._text(raw.get("_model")) or None,
            confidence_notes=confidence_notes,
        )
        return campaign, spec

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

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    def _list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return self._dedupe([self._text(item) for item in value if self._text(item)])
        if isinstance(value, str) and value.strip():
            return [self._text(value)]
        return []

    def _valid_sources(self, value: Any) -> list[str]:
        allowed = set(self.SOURCE_DESCRIPTIONS)
        return [source for source in self._list(value) if source in allowed]

    def _scoring_rubric(self, value: Any) -> dict[str, int]:
        defaults = {
            "icp_fit": 20,
            "public_evidence": 20,
            "contactability": 15,
            "pain_signal": 25,
            "solution_gap": 10,
            "trust": 10,
        }
        if not isinstance(value, dict):
            return defaults
        rubric = {}
        for key, default in defaults.items():
            try:
                score = int(value.get(key, default))
            except (TypeError, ValueError):
                score = default
            rubric[key] = max(0, min(40, score))
        return rubric

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = re.sub(r"\s+", " ", value).strip()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result
