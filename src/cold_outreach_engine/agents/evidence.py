from __future__ import annotations

import re

from cold_outreach_engine.models import CampaignContext, CampaignSpec, Evidence, EvidencePack, LeadMemory
from cold_outreach_engine.providers.base import CandidateCompany, CrawlProvider


class EvidenceAgent:
    name = "evidence_agent"

    BASE_CONTACT_TERMS = [
        "phone",
        "call",
        "email",
        "contact",
        "contact form",
        "whatsapp",
        "book",
        "schedule",
    ]

    SOLUTION_MARKERS = [
        "intercom",
        "hubspot",
        "zendesk",
        "salesforce",
        "freshdesk",
        "calendly",
        "whatsapp",
        "contact form",
        "booking",
        "chatbot",
        "live chat",
        "ivr",
    ]

    def __init__(self, crawl_provider: CrawlProvider) -> None:
        self.crawl_provider = crawl_provider

    def run(
        self, campaign: CampaignContext, spec: CampaignSpec, lead: LeadMemory
    ) -> EvidencePack:
        pages = self.crawl_provider.crawl_company(
            CandidateCompany(
                name=lead.company_name,
                country=lead.country,
                city=lead.city,
                industry=lead.industry,
                website=lead.website,
                source_url=lead.website,
                snippets=lead.facts,
            )
        )

        page_urls: list[str] = []
        evidence_ids = [evidence.id for evidence in lead.evidence]
        for page in pages:
            page_urls.append(page.url)
            if page.text and page.text[:400] not in lead.facts:
                lead.facts.append(page.text[:400])
            evidence = Evidence(
                claim=f"Public page available for evidence extraction: {page.title}",
                source_url=page.url,
                agent=self.name,
                confidence=0.75,
            )
            lead.evidence.append(evidence)
            evidence_ids.append(evidence.id)

        text = self._full_text(lead, pages)
        contact_markers = self._matched_terms(text, self._contact_terms(campaign, spec))
        pain_markers = self._matched_terms(text, self._pain_terms(spec))
        solution_markers = self._matched_terms(text, self.SOLUTION_MARKERS)
        lead.detected_tools.extend(
            marker for marker in solution_markers if marker not in lead.detected_tools
        )

        gaps = []
        if not lead.website:
            gaps.append("missing website")
        if not pages:
            gaps.append("website not crawled or no extractable page text")
        if not contact_markers:
            gaps.append("no contact-path marker found")
        if not pain_markers:
            gaps.append("no explicit campaign pain marker found")

        return EvidencePack(
            campaign_id=campaign.id,
            lead_id=lead.id,
            facts=lead.facts[:],
            page_urls=page_urls,
            contact_markers=contact_markers,
            pain_markers=pain_markers,
            solution_markers=solution_markers,
            evidence_ids=evidence_ids,
            gaps=gaps,
        )

    def _full_text(self, lead: LeadMemory, pages: list) -> str:
        return " ".join(lead.facts + [page.text for page in pages]).lower()

    def _contact_terms(self, campaign: CampaignContext, spec: CampaignSpec) -> list[str]:
        terms = self.BASE_CONTACT_TERMS[:]
        if "voice" in campaign.offer.lower() or "phone" in campaign.offer.lower():
            terms.extend(["phone", "call", "callback", "hotline"])
        if "support" in campaign.offer.lower():
            terms.extend(["support", "help", "helpdesk", "customer service"])
        return self._dedupe(terms)

    def _pain_terms(self, spec: CampaignSpec) -> list[str]:
        terms: list[str] = []
        for pain in spec.pain_hypotheses:
            terms.append(pain)
            terms.extend(self._keywords(pain))
        return self._dedupe(terms)

    def _keywords(self, phrase: str) -> list[str]:
        words = [
            word
            for word in re.split(r"[^a-z0-9]+", phrase.lower())
            if len(word) > 3 and word not in {"manual", "workflow", "customer"}
        ]
        return words

    def _matched_terms(self, text: str, terms: list[str]) -> list[str]:
        matched = []
        for term in terms:
            normalized = term.lower().strip()
            if normalized and normalized in text and normalized not in matched:
                matched.append(normalized)
        return matched[:12]

    def _dedupe(self, values: list[str]) -> list[str]:
        result: list[str] = []
        for value in values:
            cleaned = value.strip().lower()
            if cleaned and cleaned not in result:
                result.append(cleaned)
        return result
