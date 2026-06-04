from __future__ import annotations

import argparse
import json

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
    )
    result = orchestrator.run_campaign(campaign)
    print(json.dumps(to_jsonable(result), indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["sample-run"])
    args = parser.parse_args()
    if args.command == "sample-run":
        sample_run()


if __name__ == "__main__":
    main()
