from __future__ import annotations

from dataclasses import dataclass

from cold_outreach_engine.agents.buyer_signal import BuyerSignalAgent
from cold_outreach_engine.agents.clarification import ClarificationAgent
from cold_outreach_engine.agents.competitor_gap import CompetitorGapAgent
from cold_outreach_engine.agents.deduper import DeduplicationAgent
from cold_outreach_engine.agents.discovery import LeadDiscoveryAgent
from cold_outreach_engine.agents.existing_solution import ExistingSolutionAgent
from cold_outreach_engine.agents.outreach_prep import OutreachPrepAgent
from cold_outreach_engine.agents.qualification import LeadQualificationAgent
from cold_outreach_engine.agents.scoring import ScoringAgent
from cold_outreach_engine.agents.source_router import SourceRouterAgent
from cold_outreach_engine.models import (
    CampaignContext,
    ClarificationQuestion,
    LeadDossier,
    LeadMemory,
    to_jsonable,
)
from cold_outreach_engine.providers.base import CrawlProvider, SearchProvider
from cold_outreach_engine.storage import JsonStore


@dataclass
class RunResult:
    campaign: CampaignContext
    leads: list[LeadMemory]
    dossiers: list[LeadDossier]
    questions: list[ClarificationQuestion]


class LeadGenerationOrchestrator:
    def __init__(
        self,
        search_provider: SearchProvider,
        crawl_provider: CrawlProvider,
        store: JsonStore,
        max_candidates_per_run: int = 50,
        max_deep_analysis_per_run: int = 20,
    ) -> None:
        self.discovery = LeadDiscoveryAgent(search_provider)
        self.source_router = SourceRouterAgent()
        self.deduper = DeduplicationAgent()
        self.qualification = LeadQualificationAgent(crawl_provider)
        self.buyer_signal = BuyerSignalAgent()
        self.competitor_gap = CompetitorGapAgent()
        self.existing_solution = ExistingSolutionAgent()
        self.scoring = ScoringAgent()
        self.clarification = ClarificationAgent()
        self.outreach_prep = OutreachPrepAgent()
        self.store = store
        self.max_candidates_per_run = max_candidates_per_run
        self.max_deep_analysis_per_run = max_deep_analysis_per_run

    def run_campaign(self, campaign: CampaignContext) -> RunResult:
        self.store.upsert("campaigns", to_jsonable(campaign))
        source_plan = self.source_router.run(campaign)
        self.store.upsert("source_plans", to_jsonable(source_plan))

        leads = self.deduper.run(self.discovery.run(campaign))[: self.max_candidates_per_run]
        leads_to_process = leads[: self.max_deep_analysis_per_run]
        dossiers: list[LeadDossier] = []
        questions: list[ClarificationQuestion] = []

        for lead in leads_to_process:
            lead, _profile_score = self.qualification.run(campaign, lead)
            buyer_signals = self.buyer_signal.run(campaign, lead)
            solution = self.existing_solution.run(lead)
            gap = self.competitor_gap.run(campaign, lead)
            score = self.scoring.run(campaign, lead, buyer_signals, solution, gap)

            question = self.clarification.run(campaign, lead, score)
            if question:
                questions.append(question)
                self.store.upsert("clarifications", to_jsonable(question))

            dossier = self.outreach_prep.run(campaign, lead, score, gap, solution, buyer_signals)
            dossiers.append(dossier)

            self.store.upsert("leads", to_jsonable(lead))
            for signal in buyer_signals:
                self.store.upsert("buyer_signals", to_jsonable(signal))
            self.store.upsert("solution_assessments", to_jsonable(solution))
            self.store.upsert("scores", to_jsonable(score), key="lead_id")
            self.store.upsert("dossiers", to_jsonable(dossier))

        return RunResult(campaign=campaign, leads=leads_to_process, dossiers=dossiers, questions=questions)
