from __future__ import annotations

import argparse
import json

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.config import load_settings
from cold_outreach_engine.models import CampaignContext, ProviderError, to_jsonable
from cold_outreach_engine.orchestrator import LeadGenerationOrchestrator
from cold_outreach_engine.providers.factory import (
    build_crawl_provider,
    build_llm_provider,
    build_search_provider,
)
from cold_outreach_engine.storage import JsonStore


def sample_run() -> None:
    settings = load_settings()
    store = JsonStore(settings.data_dir)
    llm_provider = build_llm_provider(settings)
    campaign = CampaignContext(
        prompt="Find dynamic prospects based on the supplied ICP.",
        offer="voice AI capabilities for high-volume customer conversations",
        countries=["UAE", "Saudi Arabia", "Qatar"],
        industries=["service businesses", "operations-heavy companies"],
        ideal_company="public documentation available and growing business",
        pain_signals=["weak reachout methods", "slow response", "manual phone intake"],
        reject_rules=["no socials plus no website", "shady business", "no proper services"],
    )
    orchestrator = LeadGenerationOrchestrator(
        search_provider=build_search_provider(settings),
        crawl_provider=build_crawl_provider(settings),
        store=store,
        max_candidates_per_run=settings.max_candidates_per_run,
        max_deep_analysis_per_run=settings.max_deep_analysis_per_run,
        strategy_agent=CampaignStrategyAgent(llm_provider),
    )
    result = orchestrator.run_campaign(campaign)
    print(json.dumps(to_jsonable(result), indent=2))


def plan_prompt(prompt: str) -> None:
    settings = load_settings()
    llm_provider = build_llm_provider(settings)
    campaign, spec = CampaignStrategyAgent(llm_provider).plan(prompt)
    search_provider = build_search_provider(settings)
    crawl_provider = build_crawl_provider(settings)
    providers = [type(p).__name__ for p in getattr(search_provider, "providers", [search_provider])]

    print(
        json.dumps(
            {
                "mode": "plan_only_no_search_provider_calls",
                "campaign": to_jsonable(campaign),
                "campaign_spec": to_jsonable(spec),
                "active_search_providers": providers,
                "active_crawl_provider": type(crawl_provider).__name__,
                "active_strategy_provider": type(llm_provider).__name__
                if llm_provider
                else "heuristic_fallback",
                "caps": {
                    "max_candidates_per_run": settings.max_candidates_per_run,
                    "max_deep_analysis_per_run": settings.max_deep_analysis_per_run,
                },
            },
            indent=2,
        )
    )


def run_prompt(prompt: str, approved: bool) -> None:
    if not approved:
        raise SystemExit("Refusing to run external providers without --yes.")

    settings = load_settings()
    store = JsonStore(settings.data_dir)
    llm_provider = build_llm_provider(settings)
    campaign, spec = CampaignStrategyAgent(llm_provider).plan(prompt)

    provider_errors: list[ProviderError] = []

    def record_provider_error(error: ProviderError) -> None:
        provider_errors.append(error)
        store.upsert("provider_errors", to_jsonable(error))

    orchestrator = LeadGenerationOrchestrator(
        search_provider=build_search_provider(settings, error_sink=record_provider_error),
        crawl_provider=build_crawl_provider(settings),
        store=store,
        max_candidates_per_run=settings.max_candidates_per_run,
        max_deep_analysis_per_run=settings.max_deep_analysis_per_run,
        strategy_agent=CampaignStrategyAgent(llm_provider),
    )
    result = orchestrator.run_campaign(campaign, spec)
    statuses: dict[str, int] = {}
    for dossier in result.dossiers:
        statuses[dossier.status.value] = statuses.get(dossier.status.value, 0) + 1
    print(
        json.dumps(
            {
                "campaign_id": result.campaign.id,
                "spec_id": result.spec.id,
                "processed_leads": len(result.leads),
                "dossiers": len(result.dossiers),
                "open_questions": len(result.questions),
                "statuses": statuses,
                "provider_errors": [to_jsonable(error) for error in provider_errors],
                "saved_to": str(settings.data_dir),
            },
            indent=2,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("sample-run")

    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("prompt")

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("prompt")
    run_parser.add_argument("--yes", action="store_true", help="Approve external API usage.")

    args = parser.parse_args()
    if args.command == "sample-run":
        sample_run()
    elif args.command == "plan":
        plan_prompt(args.prompt)
    elif args.command == "run":
        run_prompt(args.prompt, args.yes)


if __name__ == "__main__":
    main()
