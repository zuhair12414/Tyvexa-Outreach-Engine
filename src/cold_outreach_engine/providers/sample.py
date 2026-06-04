from __future__ import annotations

from cold_outreach_engine.models import CampaignContext
from cold_outreach_engine.providers.base import CandidateCompany, PageSnapshot


class SampleSearchProvider:
    """Local provider used until API keys are supplied."""

    def search_companies(self, campaign: CampaignContext) -> list[CandidateCompany]:
        country = campaign.countries[0] if campaign.countries else "UAE"
        industry = campaign.industries[0] if campaign.industries else "customer service"
        city = "Helsinki" if country == "Finland" else "Dubai"
        return [
            CandidateCompany(
                name=f"Sample Growth {industry.title()} Co",
                country=country,
                city=city,
                industry=industry,
                website="https://example.com",
                source_url="sample://provider",
                snippets=[
                    "Growing business with public service pages and visible phone contact flow.",
                    "Reviews mention slow response and difficulty reaching the team.",
                ],
            ),
            CandidateCompany(
                name=f"Low Signal {industry.title()} Co",
                country=country,
                city=city,
                industry=industry,
                website=None,
                source_url="sample://provider",
                snippets=["Sparse public identity and no usable website."],
            ),
        ]


class SampleCrawlProvider:
    def crawl_company(self, company: CandidateCompany) -> list[PageSnapshot]:
        if not company.website:
            return []
        return [
            PageSnapshot(
                url=company.website,
                title=f"{company.name} homepage",
                text=(
                    "Public website lists services, phone number, WhatsApp button, "
                    "manual contact form, no visible voice AI, and no advanced booking flow."
                ),
            )
        ]


class SampleLlmProvider:
    def classify(self, task: str, payload: dict) -> dict:
        return {"task": task, "result": "sample", "payload_keys": sorted(payload.keys())}
