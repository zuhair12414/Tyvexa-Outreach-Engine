# Competitor Scan

This project borrows patterns from current lead generation and enrichment tools, without copying their outreach automation posture.

## Observed Patterns

- Clay: enrichment workflows, waterfalls across providers, reusable AI agents, prompt/version control, and score rows. Useful pattern: separate data acquisition from qualification logic.
- Apollo: large contact/company database, sales engagement, CRM-style workflow, lead routing, and follow-up surfaces. Useful pattern: leads must become pipeline objects, not just CSV rows.
- Instantly: lead finder, AI agents, AI-written openers, campaign automation, reply routing, and performance tracking. Useful pattern: outreach prep is only valuable when tied to campaign state.
- ZoomInfo Copilot: prioritized accounts based on intent and trigger signals. Useful pattern: rank accounts by signals and next-best-action, not by raw match alone.

## Product Positioning for Our Engine

The engine is not trying to beat these tools as a giant contact database. It is a dynamic, prompt-driven lead generation layer for a founder who wants high-confidence companies worth manual outreach.

## Design Implications

- Use campaign memory and reusable scoring rubrics like Clay workflows.
- Use lead/follow-up states like a lightweight CRM.
- Support provider waterfalls, but do not spend every provider on every company.
- Keep manual LinkedIn outreach, because platform scraping/automation is brittle and risky.
- Expose evidence and reasoning so the user can trust why a lead was qualified.

## Sources Reviewed

- Clay Claygent and waterfall docs.
- Apollo product/help pages.
- Instantly product/help pages.
- ZoomInfo Copilot announcement and GTM AI docs.

