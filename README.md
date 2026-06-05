# Cold Outreach Engine

Dynamic lead generation utility for an agentic AI startup. Each run starts from a campaign prompt, generates a temporary operating spec, discovers companies, builds evidence-backed lead assessments, and tracks manual outreach/follow-ups.

## What v1 Does

- Accepts a dynamic campaign prompt and uses an AI API to convert it into a per-run `CampaignSpec`; it does not depend on permanent restaurant/BPO/etc. profiles.
- Runs a controlled multi-agent pipeline: strategy, discovery, evidence, qualification, market context, dossier creation, and clarification.
- Records every run in a ledger with `CampaignRun`, `AgentStep`, and `AgentArtifact` rows so agent inputs/outputs are inspectable.
- Keeps campaign memory separate from per-lead memory so multi-lead runs do not bleed assumptions across companies.
- Produces lead dossiers with evidence packs, lead assessments, confidence, classification, manual LinkedIn guidance, and follow-up state.
- Starts with provider interfaces, AI strategy planning, and null/sample providers; real search/crawl keys can be added incrementally.

## Architecture Basis

The active design is a code-orchestrated pipeline where the campaign strategy agent is AI-first and local heuristics only validate, normalize, or provide a clearly marked fallback when no model key is configured. This follows three practical patterns from current agent frameworks:

- OpenAI Agents SDK: mix LLM-driven decisions with code orchestration when cost, speed, and predictability matter; use specialist agents for bounded tasks rather than tiny overlapping roles. Source: https://openai.github.io/openai-agents-python/multi_agent/
- LangChain/LangGraph handoffs: keep handoff context deliberate because passing full sub-agent history can create bloat and confusion. Source: https://docs.langchain.com/oss/python/langchain/multi-agent/handoffs
- AutoGen AgentChat: agents can be stateful and tool-using, but broad "kitchen sink" agents are best treated as prototypes; production workflows should have clearer custom roles. Source: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/agents.html

## Quick Start

```bash
cd /Users/zuhair12/Documents/AgenticProjects/cold-outreach-engine
PYTHONPATH=src python3 -m cold_outreach_engine.cli sample-run
PYTHONPATH=src python3 -m cold_outreach_engine.dashboard
```

Then open `http://127.0.0.1:8088`.

Plan a real prompt without spending search/crawl provider credits. If `OPENAI_API_KEY` is configured, this step can still use AI tokens because the model creates the operating spec:

```bash
PYTHONPATH=src python3 -m cold_outreach_engine.cli plan "Find me leads in Finland for service businesses looking for voice AI capabilities"
```

Run external providers only when you explicitly approve it:

```bash
PYTHONPATH=src python3 -m cold_outreach_engine.cli run "Find me leads in Finland for service businesses looking for voice AI capabilities" --yes
```

## Real API Keys Later

Copy `.env.example` to `.env` and add:

- `OPENAI_API_KEY`
- `OPENAI_MODEL`, default `gpt-4o-mini`
- `GOOGLE_PLACES_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `FIRECRAWL_API_KEY`
- optional `HUNTER_API_KEY`

The core architecture is provider-based. Google Places, Brave Search, and Firecrawl adapters are already scaffolded behind `src/cold_outreach_engine/providers`. If keys are missing, the system falls back to local sample providers.

Provider roles:

- `OPENAI_API_KEY`: AI-first prompt interpretation into campaign scope, search queries, scoring rubric, solution-gap logic, source priorities, and clarification triggers.
- `GOOGLE_PLACES_API_KEY`: location-based company discovery when the campaign spec indicates local businesses.
- `BRAVE_SEARCH_API_KEY`: broader web/company discovery for service companies, operations-heavy businesses, and niche campaigns.
- `FIRECRAWL_API_KEY`: web search fallback plus website extraction for qualification, solution detection, and buyer-signal evidence.

Cost guards:

- `LEADGEN_MAX_CANDIDATES_PER_RUN` caps candidates after dedupe.
- `LEADGEN_MAX_DEEP_ANALYSIS_PER_RUN` caps website crawls and dossier generation.
- Keep these low for the first real runs, for example `20` candidates and `5` deep analyses.

## Non-Negotiable Rules

- No LinkedIn scraping or automation. The engine only prepares manual LinkedIn outreach context.
- No factual claim without evidence URL, user answer, or campaign rule.
- Unknown data stays `unknown`, `needs_input`, or `manual_review`; it is never guessed.
- Deep crawling happens only after cheap filters pass. AI strategy planning can happen before discovery because it defines the run; later AI classification should stay behind evidence and cost gates.

## Current Agent Split

- Campaign Strategy Agent: AI API converts the prompt into a dynamic campaign operating spec; local code validates/normalizes and only falls back when no model is configured.
- Lead Discovery Agent
- Deduplication Agent
- Evidence Agent: website/public data to structured evidence pack.
- Qualification Agent: buyer signals, existing solution check, trust gates, and scoring under one decision owner.
- Market Context Agent: competitor/gap enrichment plan and future market-search hook.
- Dossier Agent: final lead dossier and manual LinkedIn outreach context.
- Clarification Layer: asks for user input when the spec or lead evidence is underspecified.

Compatibility wrappers remain for older imports, but the orchestrator now runs the 6-stage architecture above.

## Ledger-First Runtime

Each approved run writes three trace collections alongside the existing lead/dossier collections:

- `campaign_runs`: run status, current stage, provider manifest, caps, strategy source/model, and error state.
- `agent_steps`: ordered agent execution records with input artifact IDs, output artifact IDs, lead scope, status, and errors.
- `agent_artifacts`: append-only typed artifacts produced by agents, including campaign specs, source plans, leads, evidence packs, assessments, market context, dossiers, and clarification questions.

This keeps the engine framework-independent while preserving the state/checkpoint shape needed for a later LangGraph or Agents SDK migration.
