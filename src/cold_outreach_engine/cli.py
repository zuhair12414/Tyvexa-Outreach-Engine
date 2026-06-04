from __future__ import annotations

import argparse
import json

from cold_outreach_engine.agents.icp_planner import IcpPlannerAgent
from cold_outreach_engine.config import load_settings
from cold_outreach_engine.models import CampaignContext, to_jsonable
from cold_outreach_engine.orchestrator import LeadGenerationOrchestrator
from cold_outreach_engine.providers.factory import build_crawl_provider, build_search_provider
from cold_outreach_engine.storage import JsonStore


def sample_run() -> None:
    settings = load_settings()
    store = JsonStore(settings.data_dir)
    campaign = CampaignContext(
        prompt="Find dynamic voice AI prospects based on the supplied ICP.",
        offer="voice AI for missed calls, reservations, and customer support",
        countries=["UAE", "Saudi Arabia", "Qatar"],
        industries=["restaurants", "BPO", "customer service"],
        ideal_company="public documentation available and growing business",
        pain_signals=["weak reachout methods", "slow response", "reviews around weak responses"],
        reject_rules=["no socials plus no website", "shady business", "no proper services"],
    )
    orchestrator = LeadGenerationOrchestrator(
        search_provider=build_search_provider(settings),
        crawl_provider=build_crawl_provider(settings),
        store=store,
        max_candidates_per_run=settings.max_candidates_per_run,
        max_deep_analysis_per_run=settings.max_deep_analysis_per_run,
    )
    result = orchestrator.run_campaign(campaign)
    print(json.dumps(to_jsonable(result), indent=2))


def plan_prompt(prompt: str) -> None:
    settings = load_settings()
    campaign = IcpPlannerAgent().plan(prompt)
    search_provider = build_search_provider(settings)
    crawl_provider = build_crawl_provider(settings)
    providers = [type(p).__name__ for p in getattr(search_provider, "providers", [search_provider])]

    print(
        json.dumps(
            {
                "mode": "plan_only_no_api_calls",
                "campaign": to_jsonable(campaign),
                "active_search_providers": providers,
                "active_crawl_provider": type(crawl_provider).__name__,
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
    campaign = IcpPlannerAgent().plan(prompt)
    orchestrator = LeadGenerationOrchestrator(
        search_provider=build_search_provider(settings),
        crawl_provider=build_crawl_provider(settings),
        store=store,
        max_candidates_per_run=settings.max_candidates_per_run,
        max_deep_analysis_per_run=settings.max_deep_analysis_per_run,
    )
    result = orchestrator.run_campaign(campaign)
    statuses: dict[str, int] = {}
    for dossier in result.dossiers:
        statuses[dossier.status.value] = statuses.get(dossier.status.value, 0) + 1
    print(
        json.dumps(
            {
                "campaign_id": result.campaign.id,
                "processed_leads": len(result.leads),
                "dossiers": len(result.dossiers),
                "open_questions": len(result.questions),
                "statuses": statuses,
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
