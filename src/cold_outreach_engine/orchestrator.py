from __future__ import annotations

from dataclasses import dataclass

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.agents.clarification import ClarificationAgent
from cold_outreach_engine.agents.deduper import DeduplicationAgent
from cold_outreach_engine.agents.discovery import LeadDiscoveryAgent
from cold_outreach_engine.agents.evidence import EvidenceAgent
from cold_outreach_engine.agents.market_context import MarketContextAgent
from cold_outreach_engine.agents.outreach_prep import OutreachPrepAgent
from cold_outreach_engine.agents.qualification import LeadQualificationAgent
from cold_outreach_engine.models import (
    AgentArtifact,
    AgentStep,
    AgentStepStatus,
    CampaignContext,
    CampaignRun,
    CampaignRunStatus,
    CampaignSpec,
    ClarificationQuestion,
    EvidencePack,
    LeadAssessment,
    LeadDossier,
    LeadMemory,
    MarketContext,
    SourcePlan,
    to_jsonable,
    utc_now,
)
from cold_outreach_engine.providers.base import CrawlProvider, SearchProvider
from cold_outreach_engine.storage import JsonStore


@dataclass
class RunResult:
    run: CampaignRun
    campaign: CampaignContext
    spec: CampaignSpec
    leads: list[LeadMemory]
    evidence_packs: list[EvidencePack]
    assessments: list[LeadAssessment]
    market_contexts: list[MarketContext]
    dossiers: list[LeadDossier]
    questions: list[ClarificationQuestion]
    agent_steps: list[AgentStep]
    agent_artifacts: list[AgentArtifact]


class LeadGenerationOrchestrator:
    def __init__(
        self,
        search_provider: SearchProvider,
        crawl_provider: CrawlProvider,
        store: JsonStore,
        max_candidates_per_run: int = 50,
        max_deep_analysis_per_run: int = 20,
        strategy_agent: CampaignStrategyAgent | None = None,
        provider_manifest: dict | None = None,
    ) -> None:
        self.strategy = strategy_agent or CampaignStrategyAgent()
        self.discovery = LeadDiscoveryAgent(search_provider)
        self.deduper = DeduplicationAgent()
        self.evidence = EvidenceAgent(crawl_provider)
        self.qualification = LeadQualificationAgent()
        self.market_context = MarketContextAgent()
        self.clarification = ClarificationAgent()
        self.dossier = OutreachPrepAgent()
        self.store = store
        self.max_candidates_per_run = max_candidates_per_run
        self.max_deep_analysis_per_run = max_deep_analysis_per_run
        self.provider_manifest = provider_manifest or {
            "strategy": type(self.strategy).__name__,
            "search": [
                type(provider).__name__
                for provider in getattr(search_provider, "providers", [search_provider])
            ],
            "crawl": type(crawl_provider).__name__,
        }
        self._sequence = 0
        self._steps: list[AgentStep] = []
        self._artifacts: list[AgentArtifact] = []
        self._active_step: AgentStep | None = None

    def run_campaign(
        self, campaign: CampaignContext, spec: CampaignSpec | None = None
    ) -> RunResult:
        self._sequence = 0
        self._steps = []
        self._artifacts = []
        self._active_step = None
        spec = spec or self.strategy.build_spec(campaign)
        run = self._create_run(campaign, spec)

        leads_to_process: list[LeadMemory] = []
        evidence_packs: list[EvidencePack] = []
        assessments: list[LeadAssessment] = []
        market_contexts: list[MarketContext] = []
        dossiers: list[LeadDossier] = []
        questions: list[ClarificationQuestion] = []

        try:
            self._update_run(run, current_stage="campaign_strategy")
            campaign_step = self._new_step(
                run,
                agent_name=self.strategy.name,
                stage="campaign_strategy",
            )
            source_plan = self._source_plan(campaign, spec)
            self._store_campaign_plan(campaign, spec, source_plan)
            campaign_artifact = self._record_artifact(
                run,
                artifact_type="CampaignContext",
                producer_agent=self.strategy.name,
                data=campaign,
            )
            spec_artifact = self._record_artifact(
                run,
                artifact_type="CampaignSpec",
                producer_agent=self.strategy.name,
                data=spec,
            )
            source_plan_artifact = self._record_artifact(
                run,
                artifact_type="SourcePlan",
                producer_agent=self.strategy.name,
                data=source_plan,
                input_artifact_ids=[spec_artifact.id],
            )
            self._complete_step(
                campaign_step,
                [campaign_artifact.id, spec_artifact.id, source_plan_artifact.id],
            )

            self._update_run(run, current_stage="discovery")
            discovery_step = self._new_step(
                run,
                agent_name=self.discovery.name,
                stage="discovery",
                input_artifact_ids=[spec_artifact.id, source_plan_artifact.id],
            )
            discovered_leads = self.discovery.run(campaign, spec)
            discovery_artifacts = [
                self._record_artifact(
                    run,
                    artifact_type="LeadMemory",
                    producer_agent=self.discovery.name,
                    data=lead,
                    lead_id=lead.id,
                    input_artifact_ids=[spec_artifact.id, source_plan_artifact.id],
                )
                for lead in discovered_leads
            ]
            self._complete_step(discovery_step, [artifact.id for artifact in discovery_artifacts])

            self._update_run(run, current_stage="dedupe")
            dedupe_step = self._new_step(
                run,
                agent_name=self.deduper.name,
                stage="dedupe",
                input_artifact_ids=[artifact.id for artifact in discovery_artifacts],
            )
            leads = self.deduper.run(discovered_leads)[: self.max_candidates_per_run]
            dedupe_artifacts = [
                self._record_artifact(
                    run,
                    artifact_type="LeadMemory",
                    producer_agent=self.deduper.name,
                    data=lead,
                    lead_id=lead.id,
                    input_artifact_ids=[artifact.id for artifact in discovery_artifacts],
                )
                for lead in leads
            ]
            self._complete_step(dedupe_step, [artifact.id for artifact in dedupe_artifacts])

            leads_to_process = leads[: self.max_deep_analysis_per_run]
            dedupe_artifact_by_lead = {
                artifact.lead_id: artifact for artifact in dedupe_artifacts
            }

            for lead in leads_to_process:
                lead_input_artifact = dedupe_artifact_by_lead.get(lead.id)
                lead_input_ids = [spec_artifact.id]
                if lead_input_artifact:
                    lead_input_ids.append(lead_input_artifact.id)

                self._update_run(run, current_stage="evidence")
                evidence_step = self._new_step(
                    run,
                    agent_name=self.evidence.name,
                    stage="evidence",
                    lead_id=lead.id,
                    input_artifact_ids=lead_input_ids,
                )
                evidence_pack = self.evidence.run(campaign, spec, lead)
                evidence_pack_artifact = self._record_artifact(
                    run,
                    artifact_type="EvidencePack",
                    producer_agent=self.evidence.name,
                    data=evidence_pack,
                    lead_id=lead.id,
                    input_artifact_ids=lead_input_ids,
                )
                evidence_lead_artifact = self._record_artifact(
                    run,
                    artifact_type="LeadMemory",
                    producer_agent=self.evidence.name,
                    data=lead,
                    lead_id=lead.id,
                    input_artifact_ids=lead_input_ids,
                )
                self._complete_step(
                    evidence_step,
                    [evidence_pack_artifact.id, evidence_lead_artifact.id],
                )

                self._update_run(run, current_stage="qualification")
                qualification_inputs = [
                    spec_artifact.id,
                    evidence_lead_artifact.id,
                    evidence_pack_artifact.id,
                ]
                qualification_step = self._new_step(
                    run,
                    agent_name=self.qualification.name,
                    stage="qualification",
                    lead_id=lead.id,
                    input_artifact_ids=qualification_inputs,
                )
                assessment, score = self.qualification.run(campaign, spec, lead, evidence_pack)
                assessment_artifact = self._record_artifact(
                    run,
                    artifact_type="LeadAssessment",
                    producer_agent=self.qualification.name,
                    data=assessment,
                    lead_id=lead.id,
                    input_artifact_ids=qualification_inputs,
                )
                solution_artifact = self._record_artifact(
                    run,
                    artifact_type="SolutionAssessment",
                    producer_agent=self.qualification.name,
                    data=assessment.solution,
                    lead_id=lead.id,
                    input_artifact_ids=qualification_inputs,
                )
                score_artifact = self._record_artifact(
                    run,
                    artifact_type="LeadScore",
                    producer_agent=self.qualification.name,
                    data=score,
                    lead_id=lead.id,
                    input_artifact_ids=qualification_inputs,
                )
                self._complete_step(
                    qualification_step,
                    [assessment_artifact.id, solution_artifact.id, score_artifact.id],
                )

                self._update_run(run, current_stage="market_context")
                market_inputs = [spec_artifact.id, evidence_lead_artifact.id, assessment_artifact.id]
                market_step = self._new_step(
                    run,
                    agent_name=self.market_context.name,
                    stage="market_context",
                    lead_id=lead.id,
                    input_artifact_ids=market_inputs,
                )
                market_context = self.market_context.run(campaign, spec, lead, assessment)
                market_artifact = self._record_artifact(
                    run,
                    artifact_type="MarketContext",
                    producer_agent=self.market_context.name,
                    data=market_context,
                    lead_id=lead.id,
                    input_artifact_ids=market_inputs,
                )
                self._complete_step(market_step, [market_artifact.id])

                self._update_run(run, current_stage="clarification")
                clarification_inputs = [spec_artifact.id, assessment_artifact.id]
                clarification_step = self._new_step(
                    run,
                    agent_name=self.clarification.name,
                    stage="clarification",
                    lead_id=lead.id,
                    input_artifact_ids=clarification_inputs,
                )
                question = self.clarification.run(campaign, lead, assessment, spec)
                clarification_output_ids: list[str] = []
                if question:
                    questions.append(question)
                    self.store.upsert("clarifications", to_jsonable(question))
                    question_artifact = self._record_artifact(
                        run,
                        artifact_type="ClarificationQuestion",
                        producer_agent=self.clarification.name,
                        data=question,
                        lead_id=question.lead_id,
                        input_artifact_ids=clarification_inputs,
                    )
                    clarification_output_ids.append(question_artifact.id)
                self._complete_step(clarification_step, clarification_output_ids)

                self._update_run(run, current_stage="dossier")
                dossier_inputs = [
                    spec_artifact.id,
                    evidence_lead_artifact.id,
                    assessment_artifact.id,
                    market_artifact.id,
                ]
                dossier_step = self._new_step(
                    run,
                    agent_name=self.dossier.name,
                    stage="dossier",
                    lead_id=lead.id,
                    input_artifact_ids=dossier_inputs,
                )
                dossier = self.dossier.run(campaign, spec, lead, assessment, market_context)
                dossier_artifact = self._record_artifact(
                    run,
                    artifact_type="LeadDossier",
                    producer_agent=self.dossier.name,
                    data=dossier,
                    lead_id=lead.id,
                    input_artifact_ids=dossier_inputs,
                )
                self._complete_step(dossier_step, [dossier_artifact.id])

                evidence_packs.append(evidence_pack)
                assessments.append(assessment)
                market_contexts.append(market_context)
                dossiers.append(dossier)

                self._store_lead_outputs(
                    lead=lead,
                    evidence_pack=evidence_pack,
                    assessment=assessment,
                    market_context=market_context,
                    score=score,
                    dossier=dossier,
                )

            final_status = (
                CampaignRunStatus.WAITING_FOR_INPUT
                if questions
                else CampaignRunStatus.COMPLETED
            )
            self._update_run(
                run,
                status=final_status,
                current_stage="clarification"
                if final_status == CampaignRunStatus.WAITING_FOR_INPUT
                else "completed",
                completed=True,
            )
        except Exception as exc:
            if self._active_step and self._active_step.status == AgentStepStatus.RUNNING:
                self._fail_step(self._active_step, exc)
            self._update_run(
                run,
                status=CampaignRunStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
                completed=True,
            )
            raise

        return RunResult(
            run=run,
            campaign=campaign,
            spec=spec,
            leads=leads_to_process,
            evidence_packs=evidence_packs,
            assessments=assessments,
            market_contexts=market_contexts,
            dossiers=dossiers,
            questions=questions,
            agent_steps=self._steps[:],
            agent_artifacts=self._artifacts[:],
        )

    def _source_plan(self, campaign: CampaignContext, spec: CampaignSpec) -> SourcePlan:
        return SourcePlan(
            campaign_id=campaign.id,
            sources=spec.source_priorities,
            search_queries=spec.search_queries,
            rationale=(
                "Generated by Campaign Strategy Agent from the current prompt; "
                "not a hardcoded industry profile."
            ),
        )

    def _store_campaign_plan(
        self, campaign: CampaignContext, spec: CampaignSpec, source_plan: SourcePlan
    ) -> None:
        self.store.upsert("campaigns", to_jsonable(campaign))
        self.store.upsert("campaign_specs", to_jsonable(spec))
        self.store.upsert("source_plans", to_jsonable(source_plan))

    def _store_lead_outputs(
        self,
        lead: LeadMemory,
        evidence_pack: EvidencePack,
        assessment: LeadAssessment,
        market_context: MarketContext,
        score,
        dossier: LeadDossier,
    ) -> None:
        self.store.upsert("leads", to_jsonable(lead))
        self.store.upsert("evidence_packs", to_jsonable(evidence_pack), key="lead_id")
        self.store.upsert("lead_assessments", to_jsonable(assessment), key="lead_id")
        self.store.upsert("market_contexts", to_jsonable(market_context), key="lead_id")
        for signal in assessment.buyer_signals:
            self.store.upsert("buyer_signals", to_jsonable(signal))
        self.store.upsert("solution_assessments", to_jsonable(assessment.solution))
        self.store.upsert("scores", to_jsonable(score), key="lead_id")
        self.store.upsert("dossiers", to_jsonable(dossier))

    def _create_run(self, campaign: CampaignContext, spec: CampaignSpec) -> CampaignRun:
        run = CampaignRun(
            campaign_id=campaign.id,
            prompt=campaign.prompt,
            status=CampaignRunStatus.RUNNING,
            current_stage="campaign_strategy",
            caps={
                "max_candidates_per_run": self.max_candidates_per_run,
                "max_deep_analysis_per_run": self.max_deep_analysis_per_run,
            },
            providers=self.provider_manifest,
            strategy_source=spec.strategy_source,
            strategy_model=spec.strategy_model,
        )
        self.store.upsert("campaign_runs", to_jsonable(run))
        return run

    def _update_run(
        self,
        run: CampaignRun,
        status: CampaignRunStatus | None = None,
        current_stage: str | None = None,
        error: str | None = None,
        completed: bool = False,
    ) -> None:
        if status:
            run.status = status
        if current_stage:
            run.current_stage = current_stage
        if error:
            run.error = error
        if completed:
            run.completed_at = utc_now()
        run.updated_at = utc_now()
        self.store.upsert("campaign_runs", to_jsonable(run))

    def _new_step(
        self,
        run: CampaignRun,
        agent_name: str,
        stage: str,
        input_artifact_ids: list[str] | None = None,
        lead_id: str | None = None,
    ) -> AgentStep:
        self._sequence += 1
        step = AgentStep(
            run_id=run.id,
            campaign_id=run.campaign_id,
            agent_name=agent_name,
            stage=stage,
            status=AgentStepStatus.RUNNING,
            input_artifact_ids=input_artifact_ids or [],
            lead_id=lead_id,
            sequence=self._sequence,
        )
        self._active_step = step
        return step

    def _complete_step(self, step: AgentStep, output_artifact_ids: list[str]) -> None:
        step.status = AgentStepStatus.COMPLETED
        step.output_artifact_ids = output_artifact_ids
        step.completed_at = utc_now()
        self._steps.append(step)
        self.store.append_agent_step(to_jsonable(step))
        self._active_step = None

    def _fail_step(self, step: AgentStep, exc: Exception) -> None:
        step.status = AgentStepStatus.FAILED
        step.error = f"{type(exc).__name__}: {exc}"
        step.completed_at = utc_now()
        self._steps.append(step)
        self.store.append_agent_step(to_jsonable(step))
        self._active_step = None

    def _record_artifact(
        self,
        run: CampaignRun,
        artifact_type: str,
        producer_agent: str,
        data,
        lead_id: str | None = None,
        input_artifact_ids: list[str] | None = None,
    ) -> AgentArtifact:
        payload = to_jsonable(data)
        artifact = AgentArtifact(
            run_id=run.id,
            campaign_id=run.campaign_id,
            artifact_type=artifact_type,
            producer_agent=producer_agent,
            data=payload,
            source_id=payload.get("id") if isinstance(payload, dict) else None,
            lead_id=lead_id,
            input_artifact_ids=input_artifact_ids or [],
        )
        self._artifacts.append(artifact)
        self.store.append_artifact(to_jsonable(artifact))
        return artifact
