# Cold Outreach Engine

Dynamic lead generation utility for an agentic AI startup. Each run starts from a campaign prompt, builds isolated campaign context, generates evidence-backed leads, and tracks manual outreach/follow-ups.

## What v1 Does

- Accepts a dynamic campaign prompt, offer, countries, industries, pain signals, and reject rules.
- Runs a controlled multi-agent pipeline: discovery, qualification, competitor gap, existing solution check, clarification, and outreach prep.
- Keeps campaign memory separate from per-lead memory so multi-lead runs do not bleed assumptions across companies.
- Produces lead dossiers with evidence, confidence, classification, manual LinkedIn guidance, and follow-up state.
- Starts with provider interfaces and null/sample providers; real API keys can be added later.

## Quick Start

```bash
cd /Users/zuhair12/Documents/AgenticProjects/cold-outreach-engine
PYTHONPATH=src python3 -m cold_outreach_engine.cli sample-run
PYTHONPATH=src python3 -m cold_outreach_engine.dashboard
```

Then open `http://127.0.0.1:8088`.

## Real API Keys Later

Copy `.env.example` to `.env` and add:

- `OPENAI_API_KEY`
- `GOOGLE_PLACES_API_KEY`
- `BRAVE_SEARCH_API_KEY`
- `FIRECRAWL_API_KEY`
- optional `HUNTER_API_KEY`

The core architecture is provider-based. Google Places, Brave Search, and Firecrawl adapters are already scaffolded behind `src/cold_outreach_engine/providers`. If keys are missing, the system falls back to local sample providers.

Provider roles:

- `GOOGLE_PLACES_API_KEY`: local-business discovery, especially restaurants and other location-based companies.
- `BRAVE_SEARCH_API_KEY`: broader web/company discovery for BPOs, service companies, insurance, and niche campaigns.
- `FIRECRAWL_API_KEY`: website extraction for qualification, solution detection, and buyer-signal evidence.
- `OPENAI_API_KEY`: planned structured classification and prompt-to-rubric improvements.

Cost guards:

- `LEADGEN_MAX_CANDIDATES_PER_RUN` caps candidates after dedupe.
- `LEADGEN_MAX_DEEP_ANALYSIS_PER_RUN` caps website crawls and dossier generation.
- Keep these low for the first real runs, for example `20` candidates and `5` deep analyses.

## Non-Negotiable Rules

- No LinkedIn scraping or automation. The engine only prepares manual LinkedIn outreach context.
- No factual claim without evidence URL, user answer, or campaign rule.
- Unknown data stays `unknown`, `needs_input`, or `manual_review`; it is never guessed.
- Deep crawling and LLM calls happen only after cheap filters pass.

## Current Agent Split

- Campaign Planner Agent
- Source Router Agent
- Lead Discovery Agent
- Deduplication Agent
- Lead Qualification Agent
- Buyer Signal Agent
- Existing Solution Agent
- Competitor Gap Agent
- Scoring Agent
- Clarification Agent
- Outreach Prep Agent
