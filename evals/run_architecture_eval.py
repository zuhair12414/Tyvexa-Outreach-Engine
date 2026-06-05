from __future__ import annotations

import argparse
import csv
import html
import json
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory

from cold_outreach_engine.agents.campaign_strategy import CampaignStrategyAgent
from cold_outreach_engine.models import CampaignRunStatus, LeadStatus, to_jsonable
from cold_outreach_engine.orchestrator import LeadGenerationOrchestrator
from cold_outreach_engine.providers.base import CandidateCompany, PageSnapshot
from cold_outreach_engine.storage import JsonStore


EXPECTED_STAGES = [
    "campaign_strategy",
    "discovery",
    "dedupe",
    "evidence",
    "qualification",
    "market_context",
    "clarification",
    "dossier",
]


@dataclass(frozen=True)
class LeadFixture:
    key: str
    name: str
    expected_status: str
    website: str | None
    snippets: list[str]
    pages: list[PageSnapshot]
    reason: str


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    prompt: str
    expected_country: str
    expected_industries: list[str]
    expected_offer_terms: list[str]
    expected_source: str
    leads: list[LeadFixture]


class SyntheticSearchProvider:
    def __init__(self, cases: list[EvalCase]) -> None:
        self.case_by_prompt = {case.prompt: case for case in cases}
        self.search_calls = 0

    def search_companies(self, campaign, spec=None) -> list[CandidateCompany]:
        self.search_calls += 1
        case = self.case_by_prompt[campaign.prompt]
        city = city_for_country(case.expected_country)
        industry = case.expected_industries[0]
        return [
            CandidateCompany(
                name=lead.name,
                country=case.expected_country,
                city=city,
                industry=industry,
                website=lead.website,
                source_url=f"synthetic://{case.case_id}/{lead.key}",
                snippets=lead.snippets,
            )
            for lead in case.leads
        ]


class SyntheticCrawlProvider:
    def __init__(self, cases: list[EvalCase]) -> None:
        self.pages_by_website = {
            lead.website: lead.pages
            for case in cases
            for lead in case.leads
            if lead.website
        }
        self.crawl_calls = 0
        self.page_count = 0

    def crawl_company(self, company: CandidateCompany) -> list[PageSnapshot]:
        self.crawl_calls += 1
        pages = self.pages_by_website.get(company.website, [])
        self.page_count += len(pages)
        return pages


def city_for_country(country: str) -> str:
    return {
        "Finland": "Helsinki",
        "UAE": "Dubai",
        "Germany": "Berlin",
        "Qatar": "Doha",
        "Saudi Arabia": "Riyadh",
        "Netherlands": "Amsterdam",
        "Spain": "Madrid",
        "United Kingdom": "London",
        "France": "Paris",
        "Middle East": "Dubai",
    }.get(country, "Capital City")


def slug(value: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "-" for ch in value).strip("-")


def page(url: str, title: str, text: str) -> PageSnapshot:
    return PageSnapshot(url=url, title=title, text=text)


def make_leads(case_id: str, country: str, industry: str, pain_text: str) -> list[LeadFixture]:
    good_url = f"https://good-fit-{case_id}.eval.example"
    strong_url = f"https://strong-solution-{case_id}.eval.example"
    directory_url = f"https://directory-{case_id}.eval.example"
    good_name = f"{country} Growth {industry.title()} Co"
    strong_name = f"{country} Automated {industry.title()} Co"
    directory_name = f"{country} Directory {industry.title()} Listing"
    low_name = f"{country} Low Signal {industry.title()} Co"
    good_text = (
        f"{good_name} is a growing {industry} business. The website lists services, "
        "phone number, call handling, contact form, WhatsApp, booking, manual intake, "
        f"missed inbound calls, slow response loops, after-hours coverage gaps, {pain_text}, "
        "and no clearly visible mature automation platform."
    )
    strong_text = (
        f"{strong_name} is a growing {industry} business with phone, email, contact form, "
        "call handling, missed inbound calls, slow response, booking, Intercom, HubSpot, "
        "Zendesk, Salesforce, Freshdesk, live chat, and a mature customer support desk."
    )
    directory_text = (
        f"Directory of {industry} companies in {country}. This list of providers is a "
        "directory page, marketplace, and best companies article, not a buyer website."
    )
    return [
        LeadFixture(
            key="good_fit",
            name=good_name,
            expected_status="qualified",
            website=good_url,
            snippets=[
                f"Growing {industry} business with public service pages.",
                "Manual phone intake and weak customer contact flow are visible.",
            ],
            pages=[page(good_url, f"{good_name} homepage", good_text)],
            reason="Good fit: public website, contact path, pain markers, weak/manual solution.",
        ),
        LeadFixture(
            key="low_signal",
            name=low_name,
            expected_status="rejected",
            website=None,
            snippets=["Sparse public identity and no usable website."],
            pages=[],
            reason="Reject: no website/public verification path.",
        ),
        LeadFixture(
            key="strong_solution",
            name=strong_name,
            expected_status="manual_review",
            website=strong_url,
            snippets=[
                f"Public {industry} company with mature support stack visible.",
                "Pain exists, but existing automation/tooling is strong.",
            ],
            pages=[page(strong_url, f"{strong_name} homepage", strong_text)],
            reason="Manual review: mature existing solution should reduce outreach priority.",
        ),
        LeadFixture(
            key="directory",
            name=directory_name,
            expected_status="rejected",
            website=directory_url,
            snippets=["Directory of companies; list of providers; best companies article."],
            pages=[page(directory_url, directory_name, directory_text)],
            reason="Reject: non-buyer directory/listing page.",
        ),
    ]


def golden_cases() -> list[EvalCase]:
    specs = [
        (
            "finland_restaurants",
            "Find me leads in Finland for restaurant businesses looking for voice AI capabilities",
            "Finland",
            ["restaurant"],
            ["voice", "AI"],
            "google_places",
            "reservations and missed calls",
        ),
        (
            "uae_dental",
            "Find me leads in UAE for dental clinics that miss appointment calls and need voice AI reception",
            "UAE",
            ["dental clinics"],
            ["voice", "AI", "reception"],
            "google_places",
            "missed appointment calls",
        ),
        (
            "germany_property_management",
            "Find me leads in Germany for property management companies needing maintenance request automation",
            "Germany",
            ["property management"],
            ["maintenance", "automation"],
            "firecrawl_search",
            "manual maintenance requests",
        ),
        (
            "qatar_car_rental",
            "Find me leads in Qatar for car rental businesses needing after-hours booking and phone support automation",
            "Qatar",
            ["car rental"],
            ["booking", "phone", "automation"],
            "google_places",
            "after-hours booking",
        ),
        (
            "saudi_bpo_customer_service",
            "Find me leads in Saudi Arabia for BPO and customer service companies needing call QA and response automation",
            "Saudi Arabia",
            ["bpo", "customer service"],
            ["call", "automation"],
            "firecrawl_search",
            "call QA and response automation",
        ),
        (
            "netherlands_boutique_hotels",
            "Find me leads in Netherlands for boutique hotels needing multilingual guest phone support and reservation handling",
            "Netherlands",
            ["boutique hotels"],
            ["phone", "reservation"],
            "google_places",
            "guest phone support",
        ),
        (
            "spain_home_services",
            "Find me leads in Spain for home services and plumbing companies with weak missed-call recovery",
            "Spain",
            ["home services", "plumbing"],
            ["missed", "call"],
            "google_places",
            "weak missed-call recovery",
        ),
        (
            "uk_legal",
            "Find me leads in United Kingdom for small legal firms needing client intake automation and callback handling",
            "United Kingdom",
            ["small legal"],
            ["intake", "automation", "callback"],
            "firecrawl_search",
            "client intake and callback handling",
        ),
        (
            "france_ecommerce",
            "Find me leads in France for ecommerce stores looking for customer support automation",
            "France",
            ["ecommerce stores"],
            ["customer", "support", "automation"],
            "firecrawl_search",
            "customer support automation",
        ),
        (
            "middle_east_real_estate",
            "Find me leads in Middle East for real estate agencies needing an AI receptionist for inbound calls",
            "Middle East",
            ["real estate"],
            ["AI", "receptionist", "calls"],
            "google_places",
            "inbound calls and receptionist coverage",
        ),
    ]
    return [
        EvalCase(
            case_id=case_id,
            prompt=prompt,
            expected_country=country,
            expected_industries=industries,
            expected_offer_terms=offer_terms,
            expected_source=source,
            leads=make_leads(case_id, country, industries[0], pain_text),
        )
        for case_id, prompt, country, industries, offer_terms, source, pain_text in specs
    ]


def contains_all_terms(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return all(term.lower() in lowered for term in terms)


def industry_match(actual: list[str], expected: list[str]) -> bool:
    actual_text = " ".join(actual).lower()
    return all(expected_item.lower() in actual_text for expected_item in expected)


def expected_stage_sequence(lead_count: int) -> list[str]:
    stages = ["campaign_strategy", "discovery", "dedupe"]
    for _ in range(lead_count):
        stages.extend(["evidence", "qualification", "market_context", "clarification", "dossier"])
    return stages


def lead_fixture_by_name(cases: list[EvalCase]) -> dict[str, LeadFixture]:
    return {lead.name: lead for case in cases for lead in case.leads}


def evaluate_case(case: EvalCase, data_root: Path) -> tuple[dict, list[dict]]:
    case_dir = data_root / case.case_id
    store = JsonStore(case_dir)
    search_provider = SyntheticSearchProvider([case])
    crawl_provider = SyntheticCrawlProvider([case])
    strategy = CampaignStrategyAgent()
    campaign, spec = strategy.plan(case.prompt)
    orchestrator = LeadGenerationOrchestrator(
        search_provider=search_provider,
        crawl_provider=crawl_provider,
        store=store,
        max_candidates_per_run=10,
        max_deep_analysis_per_run=10,
        strategy_agent=strategy,
        provider_manifest={
            "strategy": "CampaignStrategyAgent",
            "search": ["SyntheticSearchProvider"],
            "crawl": "SyntheticCrawlProvider",
        },
    )
    result = orchestrator.run_campaign(campaign, spec)
    fixture_by_name = {lead.name: lead for lead in case.leads}
    statuses = Counter(dossier.status.value for dossier in result.dossiers)
    artifact_types = Counter(artifact.artifact_type for artifact in result.agent_artifacts)
    actual_stages = [step.stage for step in result.agent_steps]
    expected_stages = expected_stage_sequence(len(result.leads))
    ledger_complete = (
        result.run.status in {CampaignRunStatus.COMPLETED, CampaignRunStatus.WAITING_FOR_INPUT}
        and actual_stages == expected_stages
        and all(step.status.value == "completed" for step in result.agent_steps)
        and all(
            step.output_artifact_ids or step.stage == "clarification"
            for step in result.agent_steps
        )
    )
    artifact_ids = {artifact.id for artifact in result.agent_artifacts}
    artifact_reference_pass = all(
        set(step.input_artifact_ids).issubset(artifact_ids)
        and set(step.output_artifact_ids).issubset(artifact_ids)
        for step in result.agent_steps
    ) and all(
        set(artifact.input_artifact_ids).issubset(artifact_ids)
        for artifact in result.agent_artifacts
    )
    lead_artifact_types = defaultdict(set)
    for artifact in result.agent_artifacts:
        if artifact.lead_id:
            lead_artifact_types[artifact.lead_id].add(artifact.artifact_type)
    required_lead_artifacts = {
        "LeadMemory",
        "EvidencePack",
        "LeadAssessment",
        "SolutionAssessment",
        "LeadScore",
        "MarketContext",
        "LeadDossier",
    }
    lead_artifact_pass = all(
        required_lead_artifacts.issubset(lead_artifact_types[lead.id])
        for lead in result.leads
    )
    plan_provider_calls = 0
    tool_path_pass = search_provider.search_calls == 1 and crawl_provider.crawl_calls == len(result.leads)
    country_pass = case.expected_country in spec.countries or case.expected_country in campaign.countries
    industry_pass = industry_match(spec.target_industries, case.expected_industries)
    offer_pass = contains_all_terms(spec.offer, case.expected_offer_terms)
    source_pass = case.expected_source in spec.source_priorities
    prompt_accuracy = mean([country_pass, industry_pass, offer_pass, source_pass])

    lead_rows = []
    correct_leads = 0
    accepted_without_public_evidence = 0
    false_qualified = 0
    supported_claims = 0
    total_claims = 0
    evidence_source_by_id = {
        evidence.id: evidence.source_url
        for lead in result.leads
        for evidence in lead.evidence
    }
    assessments_by_lead = {assessment.lead_id: assessment for assessment in result.assessments}
    packs_by_lead = {pack.lead_id: pack for pack in result.evidence_packs}
    leads_by_id = {lead.id: lead for lead in result.leads}
    for dossier in result.dossiers:
        fixture = fixture_by_name[dossier.company_name]
        lead = leads_by_id[dossier.lead_id]
        assessment = assessments_by_lead[dossier.lead_id]
        pack = packs_by_lead[dossier.lead_id]
        expected = fixture.expected_status
        actual = dossier.status.value
        exact_match = actual == expected
        correct_leads += int(exact_match)
        if actual == "qualified" and expected != "qualified":
            false_qualified += 1
        if actual in {"qualified", "manual_review"} and not pack.page_urls:
            accepted_without_public_evidence += 1
        claim_support_results = []
        for claim in dossier.claims:
            supported = bool(claim.evidence_ids) and all(
                evidence_id in evidence_source_by_id
                and not evidence_source_by_id[evidence_id].startswith("system://")
                for evidence_id in claim.evidence_ids
            )
            claim_support_results.append(supported)
        total_claims += len(claim_support_results)
        supported_claims += sum(1 for supported in claim_support_results if supported)
        lead_rows.append(
            {
                "case_id": case.case_id,
                "prompt": case.prompt,
                "company_name": dossier.company_name,
                "expected_status": expected,
                "actual_status": actual,
                "status_match": exact_match,
                "score": dossier.score,
                "reject_reason": assessment.reject_reason or "",
                "solution_status": assessment.solution.status.value,
                "solution_type": assessment.solution.solution_type,
                "website": lead.website or "",
                "page_count": len(pack.page_urls),
                "contact_markers": "; ".join(pack.contact_markers),
                "pain_markers": "; ".join(pack.pain_markers),
                "solution_markers": "; ".join(pack.solution_markers),
                "evidence_gaps": "; ".join(pack.gaps),
                "supported_claims": all(claim_support_results) if claim_support_results else False,
                "lead_reason": fixture.reason,
                "opening_message": dossier.manual_opening_message,
            }
        )
    lead_accuracy = correct_leads / max(1, len(result.dossiers))
    claim_support_rate = supported_claims / max(1, total_claims)
    run_row = {
        "case_id": case.case_id,
        "prompt": case.prompt,
        "run_id": result.run.id,
        "run_status": result.run.status.value,
        "country_expected": case.expected_country,
        "country_actual": "; ".join(spec.countries),
        "country_pass": country_pass,
        "industries_expected": "; ".join(case.expected_industries),
        "industries_actual": "; ".join(spec.target_industries),
        "industry_pass": industry_pass,
        "offer_expected_terms": "; ".join(case.expected_offer_terms),
        "offer_actual": spec.offer,
        "offer_pass": offer_pass,
        "source_expected": case.expected_source,
        "source_actual": "; ".join(spec.source_priorities),
        "source_pass": source_pass,
        "prompt_accuracy": round(prompt_accuracy, 4),
        "ledger_complete": ledger_complete,
        "artifact_reference_pass": artifact_reference_pass,
        "lead_artifact_pass": lead_artifact_pass,
        "tool_path_pass": tool_path_pass,
        "plan_provider_calls": plan_provider_calls,
        "search_calls": search_provider.search_calls,
        "crawl_calls": crawl_provider.crawl_calls,
        "crawled_pages": crawl_provider.page_count,
        "agent_steps": len(result.agent_steps),
        "agent_artifacts": len(result.agent_artifacts),
        "artifact_types": "; ".join(f"{k}:{v}" for k, v in sorted(artifact_types.items())),
        "leads": len(result.leads),
        "qualified": statuses.get("qualified", 0),
        "manual_review": statuses.get("manual_review", 0),
        "needs_input": statuses.get("needs_input", 0),
        "rejected": statuses.get("rejected", 0),
        "lead_accuracy": round(lead_accuracy, 4),
        "false_qualified": false_qualified,
        "accepted_without_public_evidence": accepted_without_public_evidence,
        "claim_support_rate": round(claim_support_rate, 4),
    }
    return run_row, lead_rows


def bool_rate(rows: list[dict], field: str) -> float:
    return sum(1 for row in rows if row[field]) / max(1, len(rows))


def aggregate_metrics(run_rows: list[dict], lead_rows: list[dict]) -> list[dict]:
    total_leads = len(lead_rows)
    false_qualified = sum(int(row["false_qualified"]) for row in run_rows)
    accepted_without_evidence = sum(int(row["accepted_without_public_evidence"]) for row in run_rows)
    metrics = [
        ("prompt_country_accuracy", bool_rate(run_rows, "country_pass"), 0.95),
        ("prompt_industry_accuracy", bool_rate(run_rows, "industry_pass"), 0.95),
        ("prompt_offer_accuracy", bool_rate(run_rows, "offer_pass"), 0.90),
        ("source_plan_accuracy", bool_rate(run_rows, "source_pass"), 0.90),
        ("ledger_completeness", bool_rate(run_rows, "ledger_complete"), 1.00),
        ("artifact_reference_integrity", bool_rate(run_rows, "artifact_reference_pass"), 1.00),
        ("lead_artifact_coverage", bool_rate(run_rows, "lead_artifact_pass"), 1.00),
        ("tool_path_compliance", bool_rate(run_rows, "tool_path_pass"), 1.00),
        ("lead_status_accuracy", sum(row["status_match"] for row in lead_rows) / max(1, total_leads), 0.85),
        ("false_qualified_rate", 1 - (false_qualified / max(1, total_leads)), 0.95),
        ("public_evidence_gate", 1 - (accepted_without_evidence / max(1, total_leads)), 1.00),
        ("claim_support_rate", mean(float(row["claim_support_rate"]) for row in run_rows), 0.90),
    ]
    return [
        {
            "metric": name,
            "value": round(value, 4),
            "threshold": threshold,
            "pass": value >= threshold,
        }
        for name, value, threshold in metrics
    ]


def confusion_matrix(lead_rows: list[dict]) -> list[dict]:
    labels = ["qualified", "manual_review", "needs_input", "rejected"]
    counts = Counter((row["expected_status"], row["actual_status"]) for row in lead_rows)
    return [
        {
            "expected_status": expected,
            "actual_status": actual,
            "count": counts[(expected, actual)],
        }
        for expected in labels
        for actual in labels
        if counts[(expected, actual)]
    ]


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def percent(value: float) -> str:
    return f"{value * 100:.1f}%"


def bar_chart(metrics: list[dict]) -> str:
    rows = []
    for metric in metrics:
        value = float(metric["value"])
        threshold = float(metric["threshold"])
        rows.append(
            f"""
            <div class="bar-row">
              <div class="bar-label">{html.escape(metric["metric"])}</div>
              <div class="bar-track">
                <div class="bar-fill {'pass' if metric['pass'] else 'fail'}" style="width: {value * 100:.1f}%"></div>
                <div class="threshold" style="left: {threshold * 100:.1f}%"></div>
              </div>
              <div class="bar-value">{percent(value)}</div>
            </div>
            """
        )
    return "\n".join(rows)


def stacked_status_chart(run_rows: list[dict]) -> str:
    pieces = []
    for row in run_rows:
        total = max(1, int(row["leads"]))
        statuses = [
            ("qualified", int(row["qualified"]), "#87f7bf"),
            ("manual", int(row["manual_review"]), "#ffe08a"),
            ("needs", int(row["needs_input"]), "#91c7ff"),
            ("rejected", int(row["rejected"]), "#ff8f8f"),
        ]
        bars = "".join(
            f'<span title="{label}: {count}" style="width:{count / total * 100:.1f}%;background:{color}"></span>'
            for label, count, color in statuses
        )
        pieces.append(
            f"""
            <div class="stack-row">
              <div class="case-label">{html.escape(row["case_id"])}</div>
              <div class="stack-bar">{bars}</div>
            </div>
            """
        )
    return "\n".join(pieces)


def matrix_table(matrix_rows: list[dict]) -> str:
    labels = ["qualified", "manual_review", "needs_input", "rejected"]
    counts = Counter(
        (row["expected_status"], row["actual_status"])
        for row in matrix_rows
        for _ in range(int(row["count"]))
    )
    header = "".join(f"<th>{label}</th>" for label in labels)
    body = []
    for expected in labels:
        cells = "".join(f"<td>{counts[(expected, actual)]}</td>" for actual in labels)
        body.append(f"<tr><th>{expected}</th>{cells}</tr>")
    return f"<table><thead><tr><th>Expected \\ Actual</th>{header}</tr></thead><tbody>{''.join(body)}</tbody></table>"


def write_html_report(
    path: Path,
    metrics: list[dict],
    run_rows: list[dict],
    lead_rows: list[dict],
    matrix_rows: list[dict],
) -> None:
    pass_count = sum(1 for metric in metrics if metric["pass"])
    lead_accuracy = next(metric for metric in metrics if metric["metric"] == "lead_status_accuracy")
    prompt_country = next(metric for metric in metrics if metric["metric"] == "prompt_country_accuracy")
    false_qualified = next(metric for metric in metrics if metric["metric"] == "false_qualified_rate")
    html_doc = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Cold Outreach Engine Architecture Eval</title>
  <style>
    body {{ margin: 0; background: #0b0d0f; color: #f2f2ef; font-family: Inter, Arial, sans-serif; }}
    main {{ width: min(1180px, calc(100vw - 48px)); margin: 0 auto; padding: 34px 0 60px; }}
    h1 {{ font-size: 34px; margin: 0 0 8px; letter-spacing: 0; }}
    h2 {{ margin-top: 34px; font-size: 22px; }}
    p, td, th {{ color: #d8d8d2; }}
    .sub {{ color: #9ca09d; margin-bottom: 28px; }}
    .cards {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
    .card {{ border: 1px solid #33383a; background: #131619; border-radius: 8px; padding: 18px; }}
    .card .value {{ font-size: 30px; font-weight: 800; margin-top: 8px; }}
    .card .label {{ color: #a8aaa5; text-transform: uppercase; font-size: 12px; letter-spacing: .12em; }}
    .panel {{ border: 1px solid #33383a; background: #111315; border-radius: 8px; padding: 20px; margin-top: 16px; }}
    .bar-row {{ display: grid; grid-template-columns: 270px 1fr 70px; gap: 14px; align-items: center; margin: 12px 0; }}
    .bar-label {{ color: #dcdcd6; }}
    .bar-track {{ position: relative; height: 18px; background: #24282b; border-radius: 4px; overflow: hidden; }}
    .bar-fill {{ height: 100%; border-radius: 4px; }}
    .bar-fill.pass {{ background: #87f7bf; }}
    .bar-fill.fail {{ background: #ff8f8f; }}
    .threshold {{ position: absolute; top: 0; bottom: 0; width: 2px; background: #fff; opacity: .9; }}
    .bar-value {{ text-align: right; font-variant-numeric: tabular-nums; }}
    .stack-row {{ display: grid; grid-template-columns: 270px 1fr; gap: 14px; align-items: center; margin: 12px 0; }}
    .case-label {{ color: #dcdcd6; }}
    .stack-bar {{ display: flex; height: 22px; border-radius: 4px; overflow: hidden; background: #24282b; }}
    .stack-bar span {{ display: block; min-width: 1px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #33383a; padding: 10px; text-align: left; }}
    th {{ background: #171a1d; color: #f2f2ef; }}
    .fail-row td {{ color: #ffd4d4; }}
    .small {{ font-size: 13px; color: #a8aaa5; }}
  </style>
</head>
<body>
<main>
  <h1>Cold Outreach Engine Architecture Eval</h1>
  <div class="sub">Offline synthetic evaluation. No live APIs, no paid model calls.</div>

  <section class="cards">
    <div class="card"><div class="label">Metric Gates Passed</div><div class="value">{pass_count}/{len(metrics)}</div></div>
    <div class="card"><div class="label">Lead Status Accuracy</div><div class="value">{percent(float(lead_accuracy["value"]))}</div></div>
    <div class="card"><div class="label">Country Parse Accuracy</div><div class="value">{percent(float(prompt_country["value"]))}</div></div>
    <div class="card"><div class="label">False Qualified Guard</div><div class="value">{percent(float(false_qualified["value"]))}</div></div>
  </section>

  <h2>Metric Gates</h2>
  <div class="panel">{bar_chart(metrics)}</div>

  <h2>Lead Outcomes Per Run</h2>
  <div class="panel">
    <div class="small">Green = qualified, yellow = manual review, blue = needs input, red = rejected.</div>
    {stacked_status_chart(run_rows)}
  </div>

  <h2>Status Confusion Matrix</h2>
  <div class="panel">{matrix_table(matrix_rows)}</div>

  <h2>Run Details</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Case</th><th>Prompt Accuracy</th><th>Ledger</th><th>Lead Accuracy</th><th>False Qualified</th><th>Search/Crawl</th></tr></thead>
      <tbody>
        {''.join(
            f"<tr class='{'' if float(row['lead_accuracy']) >= 0.85 else 'fail-row'}'>"
            f"<td>{html.escape(row['case_id'])}</td>"
            f"<td>{float(row['prompt_accuracy']) * 100:.1f}%</td>"
            f"<td>{row['ledger_complete']}</td>"
            f"<td>{float(row['lead_accuracy']) * 100:.1f}%</td>"
            f"<td>{row['false_qualified']}</td>"
            f"<td>{row['search_calls']} / {row['crawl_calls']}</td>"
            f"</tr>"
            for row in run_rows
        )}
      </tbody>
    </table>
  </div>

  <h2>Top Failure Examples</h2>
  <div class="panel">
    <table>
      <thead><tr><th>Case</th><th>Company</th><th>Expected</th><th>Actual</th><th>Reason</th></tr></thead>
      <tbody>
        {''.join(
            f"<tr class='fail-row'><td>{html.escape(row['case_id'])}</td>"
            f"<td>{html.escape(row['company_name'])}</td>"
            f"<td>{html.escape(row['expected_status'])}</td>"
            f"<td>{html.escape(row['actual_status'])}</td>"
            f"<td>{html.escape(row['lead_reason'])}</td></tr>"
            for row in lead_rows
            if not row['status_match']
        ) or '<tr><td colspan="5">No lead classification failures.</td></tr>'}
      </tbody>
    </table>
  </div>
</main>
</body>
</html>
"""
    path.write_text(html_doc)


def run_eval(output_dir: Path, clean: bool = False) -> dict:
    if clean and output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cases = golden_cases()
    run_rows: list[dict] = []
    lead_rows: list[dict] = []
    with TemporaryDirectory(prefix="cold-outreach-eval-") as temp_dir:
        data_root = Path(temp_dir)
        for case in cases:
            run_row, case_leads = evaluate_case(case, data_root)
            run_rows.append(run_row)
            lead_rows.extend(case_leads)
    metrics = aggregate_metrics(run_rows, lead_rows)
    matrix_rows = confusion_matrix(lead_rows)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cases": len(cases),
        "leads": len(lead_rows),
        "metrics_passed": sum(1 for metric in metrics if metric["pass"]),
        "metrics_total": len(metrics),
        "metric_values": {metric["metric"]: metric["value"] for metric in metrics},
    }
    write_csv(output_dir / "run_metrics.csv", run_rows)
    write_csv(output_dir / "lead_metrics.csv", lead_rows)
    write_csv(output_dir / "summary_metrics.csv", metrics)
    write_csv(output_dir / "confusion_matrix.csv", matrix_rows)
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    write_html_report(output_dir / "architecture_eval_report.html", metrics, run_rows, lead_rows, matrix_rows)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run offline architecture and quality evals.")
    parser.add_argument(
        "--output-dir",
        default="eval_outputs/architecture_eval_latest",
        help="Directory for CSV/HTML evaluation outputs.",
    )
    parser.add_argument("--clean", action="store_true", help="Clear output directory before writing.")
    args = parser.parse_args()
    summary = run_eval(Path(args.output_dir), clean=args.clean)
    print(json.dumps(to_jsonable(summary), indent=2, sort_keys=True))
    print(f"report={Path(args.output_dir) / 'architecture_eval_report.html'}")


if __name__ == "__main__":
    main()
