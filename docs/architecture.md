# Architecture

## Runtime Flow

```text
Campaign Prompt
  -> Campaign Planner
  -> Source Router
  -> Lead Discovery Agent
  -> Deduplication Agent
  -> Lead Qualification Agent
  -> Buyer Signal Agent
  -> Competitor Gap Agent
  -> Existing Solution Agent
  -> Scoring Agent
  -> Clarification Agent
  -> Outreach Prep Agent
  -> Lead Dossier + Follow-up Tracker
```

## Context Boundaries

Campaign memory is shared across one lead generation attempt:

- offer
- countries and regions
- target industries
- ideal company profile
- pain signals
- reject rules
- user answers that apply to the whole campaign

Lead memory is isolated per company:

- known facts
- evidence URLs
- detected tools
- competitor observations
- open questions
- final classification

Agents may only use campaign memory, lead memory, evidence, or explicit user answers. If evidence is missing, the agent must return `unknown`, `needs_input`, or `manual_review`.

## Scoring

Score components:

- ICP fit: 0-2
- contactability: 0-2
- buyer signal: 0-3
- existing solution weakness: 0-2
- competitor pressure: 0-2
- evidence quality: 0-2
- trust penalty: -3 to 0

Final statuses:

- `qualified`
- `manual_review`
- `needs_input`
- `rejected`

## Agent Split

- Campaign Planner: turns natural language into structured campaign rules.
- Source Router: chooses source families and query templates by vertical.
- Lead Discovery: gathers raw candidate companies.
- Deduplication: merges same company across sources.
- Lead Qualification: crawls public website data and builds basic profile evidence.
- Buyer Signal: detects offer-specific buying signals such as phone dependency or slow response.
- Existing Solution: classifies public solution markers with type and outreach implication.
- Competitor Gap: compares local/category alternatives when search providers are connected.
- Scoring: applies the explicit rubric and final status.
- Clarification: asks only when user input changes classification.
- Outreach Prep: creates evidence-linked lead dossiers and manual LinkedIn guidance.

## Clarification Loop

The clarification agent asks only when an answer changes classification. It must label each question as:

- `campaign_wide`: answer becomes a reusable campaign rule.
- `lead_specific`: answer applies only to the current company.

## Follow-up Tracker

Each qualified lead can move through:

- `new`
- `linkedin_searched`
- `contacted`
- `follow_up_due`
- `replied`
- `not_fit`
- `won`
- `lost`
