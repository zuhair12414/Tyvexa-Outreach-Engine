from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LeadStatus(str, Enum):
    CANDIDATE = "candidate"
    QUALIFIED = "qualified"
    MANUAL_REVIEW = "manual_review"
    NEEDS_INPUT = "needs_input"
    REJECTED = "rejected"


class SolutionStatus(str, Enum):
    NO_SOLUTION = "no_solution"
    WEAK_SOLUTION = "weak_solution"
    STRONG_SOLUTION = "strong_solution"
    UNKNOWN = "unknown"


class FollowUpStage(str, Enum):
    NEW = "new"
    LINKEDIN_SEARCHED = "linkedin_searched"
    CONTACTED = "contacted"
    FOLLOW_UP_DUE = "follow_up_due"
    REPLIED = "replied"
    NOT_FIT = "not_fit"
    WON = "won"
    LOST = "lost"


@dataclass
class Evidence:
    claim: str
    source_url: str
    agent: str
    confidence: float
    captured_at: str = field(default_factory=utc_now)
    id: str = field(default_factory=lambda: f"ev_{uuid4().hex[:10]}")


@dataclass
class SourcePlan:
    campaign_id: str
    sources: list[str]
    search_queries: list[str]
    rationale: str
    id: str = field(default_factory=lambda: f"src_{uuid4().hex[:10]}")


@dataclass
class BuyerSignal:
    lead_id: str
    name: str
    strength: int
    reason: str
    evidence_ids: list[str]
    id: str = field(default_factory=lambda: f"sig_{uuid4().hex[:10]}")


@dataclass
class SolutionAssessment:
    lead_id: str
    status: SolutionStatus
    solution_type: str
    detected_tools: list[str]
    outreach_implication: str
    evidence_ids: list[str]
    id: str = field(default_factory=lambda: f"sol_{uuid4().hex[:10]}")


@dataclass
class CampaignContext:
    prompt: str
    offer: str
    countries: list[str]
    industries: list[str]
    ideal_company: str
    pain_signals: list[str]
    reject_rules: list[str]
    outreach_channel: str = "manual_linkedin"
    id: str = field(default_factory=lambda: f"camp_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=utc_now)
    reusable_rules: list[str] = field(default_factory=list)


@dataclass
class LeadMemory:
    campaign_id: str
    company_name: str
    country: str | None = None
    city: str | None = None
    industry: str | None = None
    website: str | None = None
    socials: list[str] = field(default_factory=list)
    facts: list[str] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    detected_tools: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"lead_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=utc_now)


@dataclass
class LeadScore:
    lead_id: str
    status: LeadStatus
    total: int
    reasons: list[str]
    reject_reason: str | None = None
    solution_status: SolutionStatus = SolutionStatus.UNKNOWN
    component_scores: dict[str, int] = field(default_factory=dict)
    rubric_version: str = "v1"


@dataclass
class DossierClaim:
    text: str
    evidence_ids: list[str]
    confidence: float


@dataclass
class ClarificationQuestion:
    campaign_id: str
    lead_id: str | None
    question: str
    scope: str
    status: str = "open"
    answer: str | None = None
    id: str = field(default_factory=lambda: f"q_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=utc_now)


@dataclass
class LeadDossier:
    campaign_id: str
    lead_id: str
    company_name: str
    status: LeadStatus
    score: int
    why_this_lead: str
    evidence_summary: list[str]
    competitor_gap: str
    solution_assessment: str
    linkedin_persona: str
    linkedin_search_hint: str
    manual_opening_message: str
    claims: list[DossierClaim] = field(default_factory=list)
    follow_up_stage: FollowUpStage = FollowUpStage.NEW
    id: str = field(default_factory=lambda: f"dos_{uuid4().hex[:10]}")
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if hasattr(value, "__dataclass_fields__"):
        return to_jsonable(asdict(value))
    return value
