from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import pytest

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.models import (
    AgentStepStatus,
    CampaignContext,
    CampaignRunStatus,
    CampaignSpec,
    LeadStatus,
    to_jsonable,
)
from cold_outreach_engine.orchestrator import LeadGenerationOrchestrator
from cold_outreach_engine.providers.base import CandidateCompany, PageSnapshot
from cold_outreach_engine.providers.sample import SampleCrawlProvider, SampleSearchProvider
from cold_outreach_engine.storage import JsonStore


def run_sample_campaign(tmp_path: Path, campaign: CampaignContext | None = None):
    store = JsonStore(tmp_path)
    strategy = CampaignStrategyAgent()
    campaign = campaign or CampaignContext(
        prompt="Find me leads in Finland for restaurant businesses looking for voice AI capabilities",
        offer="voice AI capabilities",
        countries=["Finland"],
        industries=["restaurant"],
        ideal_company="public documentation available and growing business",
        pain_signals=[
            "missed inbound calls",
            "phone dependency",
            "manual call handling",
        ],
        reject_rules=[
            "no public verification path",
            "no clear service offering",
            "no usable contact path",
        ],
    )
    spec = strategy.build_spec(campaign)
    orchestrator = LeadGenerationOrchestrator(
        search_provider=SampleSearchProvider(),
        crawl_provider=SampleCrawlProvider(),
        store=store,
        max_candidates_per_run=20,
        max_deep_analysis_per_run=5,
        strategy_agent=strategy,
    )
    return orchestrator.run_campaign(campaign, spec), store


def test_campaign_strategy_fallback_extracts_dynamic_prompt_context() -> None:
    campaign, spec = CampaignStrategyAgent().plan(
        "Find me leads in Finland for restaurant businesses looking for voice AI capabilities"
    )

    assert campaign.countries == ["Finland"]
    assert campaign.industries == ["restaurant"]
    assert campaign.offer == "voice AI capabilities"
    assert "missed inbound calls" in campaign.pain_signals
    assert "google_places" in spec.source_priorities
    assert spec.search_queries[0] == "restaurant Finland voice AI capabilities"
    assert spec.strategy_source == "heuristic_fallback"
    assert any("No LLM provider configured" in note for note in spec.confidence_notes)


def test_campaign_strategy_extracts_vertical_specific_prompts_without_clarification() -> None:
    cases = [
        (
            "Find me leads in UAE for dental clinics that miss appointment calls and need voice AI reception",
            ["dental clinics"],
            "voice AI reception",
            "google_places",
        ),
        (
            "Find me leads in Netherlands for boutique hotels needing multilingual guest phone support and reservation handling",
            ["boutique hotels"],
            "multilingual guest phone support and reservation handling",
            "google_places",
        ),
        (
            "Find me leads in France for ecommerce stores looking for customer support automation",
            ["ecommerce stores"],
            "customer support automation",
            "firecrawl_search",
        ),
        (
            "Find me leads in Spain for home services and plumbing companies with weak missed-call recovery",
            ["home services", "plumbing"],
            "weak missed-call recovery",
            "google_places",
        ),
    ]

    for prompt, expected_industries, expected_offer, expected_source in cases:
        campaign, spec = CampaignStrategyAgent().plan(prompt)

        assert campaign.industries == expected_industries
        assert campaign.offer == expected_offer
        assert expected_source in spec.source_priorities
        assert "unspecified target businesses" not in campaign.industries


def test_campaign_strategy_ai_output_is_schema_normalized() -> None:
    class FakeLlmProvider:
        def classify(self, task: str, payload: dict) -> dict:
            assert task == "campaign_strategy"
            assert "prompt" in payload
            return {
                "offer": "voice AI receptionist",
                "countries": ["Pakistan"],
                "target_locations": ["Islamabad"],
                "target_industries": ["restaurants", "cafes"],
                "pain_hypotheses": ["missed calls", "manual reservations"],
                "solution_gaps": ["no delivery app", "no phone automation"],
                "good_lead_traits": ["public menu", "visible phone number"],
                "reject_rules": ["no website", "unclear business identity"],
                "source_priorities": ["google_places", "linkedin", "firecrawl_search"],
                "search_queries": [
                    "restaurants Islamabad no delivery app",
                    "cafes Islamabad official website phone",
                ],
                "evidence_requirements": ["website evidence", "contact evidence"],
                "buyer_personas": ["owner", "manager"],
                "scoring_rubric": {
                    "icp_fit": 25,
                    "public_evidence": 20,
                    "contactability": 15,
                    "pain_signal": 20,
                    "solution_gap": 10,
                    "trust": 10,
                },
                "clarification_triggers": ["thin public evidence"],
                "confidence_notes": ["city-level campaign"],
                "_model": "fake-strong-model",
            }

    campaign, spec = CampaignStrategyAgent(FakeLlmProvider()).plan(
        "Find me leads in Islamabad for restaurants that do not have a delivery app"
    )

    assert campaign.countries == ["Islamabad"]
    assert campaign.industries == ["restaurants", "cafes"]
    assert campaign.offer == "voice AI receptionist"
    assert spec.strategy_source == "ai_api"
    assert spec.strategy_model == "fake-strong-model"
    assert spec.target_locations == ["Islamabad"]
    assert spec.countries == ["Pakistan"]
    assert "linkedin" not in spec.source_priorities
    assert spec.source_priorities == ["google_places", "firecrawl_search"]
    assert spec.scoring_rubric["icp_fit"] == 25


def test_orchestrator_records_complete_ledger_and_preserves_legacy_outputs(tmp_path: Path) -> None:
    result, store = run_sample_campaign(tmp_path)

    assert result.run.status == CampaignRunStatus.COMPLETED
    assert result.run.current_stage == "completed"
    assert len(result.leads) == 2
    assert len(result.dossiers) == 2
    assert len(result.questions) == 0

    assert len(store.read_collection("campaign_runs")) == 1
    assert len(store.read_collection("agent_steps")) == len(result.agent_steps)
    assert len(store.read_collection("agent_artifacts")) == len(result.agent_artifacts)
    assert len(store.read_collection("leads")) == 2
    assert len(store.read_collection("dossiers")) == 2
    assert len(store.read_collection("evidence_packs")) == 2
    assert len(store.read_collection("lead_assessments")) == 2


def test_agent_stage_order_and_outputs_are_explicit(tmp_path: Path) -> None:
    result, _ = run_sample_campaign(tmp_path)

    expected_stage_order = [
        "campaign_strategy",
        "discovery",
        "dedupe",
        "evidence",
        "qualification",
        "market_context",
        "clarification",
        "dossier",
        "evidence",
        "qualification",
        "market_context",
        "clarification",
        "dossier",
    ]
    assert [step.stage for step in result.agent_steps] == expected_stage_order
    assert [step.sequence for step in result.agent_steps] == list(range(1, 14))
    assert all(step.status == AgentStepStatus.COMPLETED for step in result.agent_steps)

    for step in result.agent_steps:
        if step.stage == "clarification":
            continue
        assert step.output_artifact_ids, f"{step.stage} did not emit artifacts"


def test_artifact_references_are_valid_and_lead_bound(tmp_path: Path) -> None:
    result, _ = run_sample_campaign(tmp_path)
    artifact_ids = {artifact.id for artifact in result.agent_artifacts}
    lead_ids = {lead.id for lead in result.leads}

    for step in result.agent_steps:
        assert set(step.input_artifact_ids).issubset(artifact_ids)
        assert set(step.output_artifact_ids).issubset(artifact_ids)

    for artifact in result.agent_artifacts:
        assert artifact.run_id == result.run.id
        assert artifact.campaign_id == result.campaign.id
        assert set(artifact.input_artifact_ids).issubset(artifact_ids)
        if artifact.lead_id is not None:
            assert artifact.lead_id in lead_ids

    by_lead: dict[str, Counter[str]] = defaultdict(Counter)
    for artifact in result.agent_artifacts:
        if artifact.lead_id:
            by_lead[artifact.lead_id][artifact.artifact_type] += 1

    required = {
        "LeadMemory",
        "EvidencePack",
        "LeadAssessment",
        "SolutionAssessment",
        "LeadScore",
        "MarketContext",
        "LeadDossier",
    }
    assert set(by_lead) == lead_ids
    for lead_id, counts in by_lead.items():
        assert required.issubset(counts), f"{lead_id} missing {required - set(counts)}"


def test_evidence_and_qualification_are_conservative_for_low_signal_leads(tmp_path: Path) -> None:
    result, _ = run_sample_campaign(tmp_path)
    dossiers_by_status = {dossier.status: dossier for dossier in result.dossiers}

    qualified = dossiers_by_status[LeadStatus.QUALIFIED]
    rejected = dossiers_by_status[LeadStatus.REJECTED]

    assert qualified.score >= 70
    assert "Worth comparing notes?" in qualified.manual_opening_message
    assert "No outreach recommended" in rejected.manual_opening_message

    rejected_assessment = next(
        assessment for assessment in result.assessments if assessment.lead_id == rejected.lead_id
    )
    assert rejected_assessment.reject_reason == (
        "Rejected by rubric: no website/public verification path."
    )


def test_strong_existing_solution_is_capped_to_manual_review(tmp_path: Path) -> None:
    from cold_outreach_engine.providers.base import CandidateCompany, PageSnapshot

    class StrongSolutionSearchProvider:
        def search_companies(self, campaign, spec=None):
            return [
                CandidateCompany(
                    name="Mature Support Stack Restaurant",
                    country="Finland",
                    city="Helsinki",
                    industry="restaurant",
                    website="https://mature.example",
                    source_url="synthetic://strong-solution",
                    snippets=[
                        "Restaurant with missed inbound calls, phone booking, and mature tooling."
                    ],
                )
            ]

    class StrongSolutionCrawlProvider:
        def crawl_company(self, company):
            return [
                PageSnapshot(
                    url="https://mature.example",
                    title="Mature Support Stack Restaurant",
                    text=(
                        "Restaurant with phone, call handling, missed inbound calls, "
                        "booking, Intercom, HubSpot, Zendesk, Salesforce, and Freshdesk."
                    ),
                )
            ]

    store = JsonStore(tmp_path)
    campaign = CampaignContext(
        prompt="Find me leads in Finland for restaurant businesses looking for voice AI capabilities",
        offer="voice AI capabilities",
        countries=["Finland"],
        industries=["restaurant"],
        ideal_company="public documentation available and growing business",
        pain_signals=["missed inbound calls", "phone dependency", "manual call handling"],
        reject_rules=["no public verification path", "no usable contact path"],
    )
    spec = CampaignStrategyAgent().build_spec(campaign)
    result = LeadGenerationOrchestrator(
        search_provider=StrongSolutionSearchProvider(),
        crawl_provider=StrongSolutionCrawlProvider(),
        store=store,
        max_candidates_per_run=5,
        max_deep_analysis_per_run=5,
        strategy_agent=CampaignStrategyAgent(),
    ).run_campaign(campaign, spec)

    dossier = result.dossiers[0]
    assessment = result.assessments[0]
    assert dossier.status == LeadStatus.MANUAL_REVIEW
    assert dossier.score == 65
    assert assessment.solution.status.value == "strong_solution"
    assert assessment.component_scores["strong_solution_cap"] < 0


def test_underspecified_campaign_creates_clarification_and_waiting_run(tmp_path: Path) -> None:
    campaign, spec = CampaignStrategyAgent().plan(
        "Find me leads for businesses looking for workflow automation"
    )
    store = JsonStore(tmp_path)
    orchestrator = LeadGenerationOrchestrator(
        search_provider=SampleSearchProvider(),
        crawl_provider=SampleCrawlProvider(),
        store=store,
        max_candidates_per_run=20,
        max_deep_analysis_per_run=2,
        strategy_agent=CampaignStrategyAgent(),
    )

    result = orchestrator.run_campaign(campaign, spec)

    assert result.run.status == CampaignRunStatus.WAITING_FOR_INPUT
    assert result.run.current_stage == "clarification"
    assert len(result.questions) >= 1
    assert any(question.scope == "campaign_wide" for question in result.questions)
    assert store.read_collection("clarifications")
    assert any(
        artifact.artifact_type == "ClarificationQuestion"
        for artifact in result.agent_artifacts
    )


def test_failed_agent_step_and_run_are_persisted(tmp_path: Path) -> None:
    class CrashingCrawlProvider:
        def crawl_company(self, company: CandidateCompany) -> list[PageSnapshot]:
            raise RuntimeError("crawl exploded")

    store = JsonStore(tmp_path)
    campaign = CampaignContext(
        prompt="Find me leads in Finland for restaurant businesses looking for voice AI",
        offer="voice AI",
        countries=["Finland"],
        industries=["restaurant"],
        ideal_company="public documentation available",
        pain_signals=["missed inbound calls"],
        reject_rules=["no public verification path"],
    )
    spec = CampaignStrategyAgent().build_spec(campaign)
    orchestrator = LeadGenerationOrchestrator(
        search_provider=SampleSearchProvider(),
        crawl_provider=CrashingCrawlProvider(),
        store=store,
        max_candidates_per_run=20,
        max_deep_analysis_per_run=2,
        strategy_agent=CampaignStrategyAgent(),
    )

    with pytest.raises(RuntimeError, match="crawl exploded"):
        orchestrator.run_campaign(campaign, spec)

    runs = store.read_collection("campaign_runs")
    steps = store.read_collection("agent_steps")
    assert runs[0]["status"] == "failed"
    assert runs[0]["current_stage"] == "evidence"
    assert "RuntimeError: crawl exploded" in runs[0]["error"]
    assert steps[-1]["stage"] == "evidence"
    assert steps[-1]["status"] == "failed"
    assert "RuntimeError: crawl exploded" in steps[-1]["error"]


def test_json_store_artifact_filters(tmp_path: Path) -> None:
    result, store = run_sample_campaign(tmp_path)
    first_lead = result.leads[0]

    assert len(store.read_agent_steps(run_id=result.run.id)) == len(result.agent_steps)
    assert len(store.read_agent_steps(lead_id=first_lead.id)) == 5
    assert len(store.read_artifacts(run_id=result.run.id)) == len(result.agent_artifacts)
    assert len(store.read_artifacts(lead_id=first_lead.id, artifact_type="LeadDossier")) == 1
    assert len(store.read_artifacts(agent_name="qualification_agent")) == 6


def test_to_jsonable_serializes_nested_enums(tmp_path: Path) -> None:
    result, _ = run_sample_campaign(tmp_path)
    payload = to_jsonable(result)

    assert payload["run"]["status"] == "completed"
    assert payload["dossiers"][0]["status"] in {
        "qualified",
        "manual_review",
        "needs_input",
        "rejected",
    }
    assert payload["agent_steps"][0]["status"] == "completed"
