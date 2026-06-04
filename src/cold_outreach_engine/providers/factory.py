from __future__ import annotations

import httpx

from cold_outreach_engine.config import Settings
from cold_outreach_engine.models import CampaignContext, CampaignSpec, ProviderError
from cold_outreach_engine.providers.base import (
    CandidateCompany,
    CrawlProvider,
    LlmProvider,
    SearchProvider,
)
from cold_outreach_engine.providers.brave_search import BraveSearchProvider
from cold_outreach_engine.providers.firecrawl import FirecrawlProvider, FirecrawlSearchProvider
from cold_outreach_engine.providers.google_places import GooglePlacesProvider
from cold_outreach_engine.providers.openai_llm import OpenAILlmProvider
from cold_outreach_engine.providers.sample import SampleCrawlProvider, SampleSearchProvider


class CompositeSearchProvider:
    def __init__(self, providers: list[SearchProvider], error_sink=None) -> None:
        self.providers = providers
        self.error_sink = error_sink

    def search_companies(
        self, campaign: CampaignContext, spec: CampaignSpec | None = None
    ) -> list[CandidateCompany]:
        candidates: list[CandidateCompany] = []
        for provider in self.providers:
            try:
                candidates.extend(provider.search_companies(campaign, spec))
            except httpx.HTTPStatusError as exc:
                body = exc.response.text[:500] if exc.response is not None else ""
                self._record_error(
                    campaign,
                    provider,
                    f"{exc}. Response body: {body}",
                    status_code=exc.response.status_code,
                    url=str(exc.request.url),
                )
            except Exception as exc:
                self._record_error(campaign, provider, str(exc))
        return candidates

    def _record_error(
        self,
        campaign: CampaignContext,
        provider: SearchProvider,
        message: str,
        status_code: int | None = None,
        url: str | None = None,
    ) -> None:
        if not self.error_sink:
            return
        error = ProviderError(
            campaign_id=campaign.id,
            provider=type(provider).__name__,
            message=message,
            status_code=status_code,
            url=url,
        )
        self.error_sink(error)


def build_search_provider(settings: Settings, error_sink=None) -> SearchProvider:
    providers: list[SearchProvider] = []
    if settings.google_places_api_key:
        providers.append(GooglePlacesProvider(settings.google_places_api_key))
    if settings.brave_search_api_key:
        providers.append(BraveSearchProvider(settings.brave_search_api_key))
    if settings.firecrawl_api_key:
        providers.append(FirecrawlSearchProvider(settings.firecrawl_api_key))
    if not providers:
        return SampleSearchProvider()
    return CompositeSearchProvider(providers, error_sink=error_sink)


def build_crawl_provider(settings: Settings) -> CrawlProvider:
    if settings.firecrawl_api_key:
        return FirecrawlProvider(settings.firecrawl_api_key)
    return SampleCrawlProvider()


def build_llm_provider(settings: Settings) -> LlmProvider | None:
    if settings.openai_api_key:
        return OpenAILlmProvider(settings.openai_api_key, settings.openai_model)
    return None
