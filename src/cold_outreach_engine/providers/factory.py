from __future__ import annotations

from cold_outreach_engine.config import Settings
from cold_outreach_engine.models import CampaignContext
from cold_outreach_engine.providers.base import CandidateCompany, CrawlProvider, SearchProvider
from cold_outreach_engine.providers.brave_search import BraveSearchProvider
from cold_outreach_engine.providers.firecrawl import FirecrawlProvider, FirecrawlSearchProvider
from cold_outreach_engine.providers.google_places import GooglePlacesProvider
from cold_outreach_engine.providers.sample import SampleCrawlProvider, SampleSearchProvider


class CompositeSearchProvider:
    def __init__(self, providers: list[SearchProvider]) -> None:
        self.providers = providers

    def search_companies(self, campaign: CampaignContext) -> list[CandidateCompany]:
        candidates: list[CandidateCompany] = []
        for provider in self.providers:
            candidates.extend(provider.search_companies(campaign))
        return candidates


def build_search_provider(settings: Settings) -> SearchProvider:
    providers: list[SearchProvider] = []
    if settings.google_places_api_key:
        providers.append(GooglePlacesProvider(settings.google_places_api_key))
    if settings.brave_search_api_key:
        providers.append(BraveSearchProvider(settings.brave_search_api_key))
    if settings.firecrawl_api_key:
        providers.append(FirecrawlSearchProvider(settings.firecrawl_api_key))
    if not providers:
        return SampleSearchProvider()
    return CompositeSearchProvider(providers)


def build_crawl_provider(settings: Settings) -> CrawlProvider:
    if settings.firecrawl_api_key:
        return FirecrawlProvider(settings.firecrawl_api_key)
    return SampleCrawlProvider()
