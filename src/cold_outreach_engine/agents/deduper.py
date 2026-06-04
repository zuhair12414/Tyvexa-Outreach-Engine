from __future__ import annotations

import re
from urllib.parse import urlparse

from cold_outreach_engine.models import Evidence, LeadMemory


class DeduplicationAgent:
    name = "deduplication_agent"

    def run(self, leads: list[LeadMemory]) -> list[LeadMemory]:
        merged: dict[str, LeadMemory] = {}
        for lead in leads:
            key = self._key_for(lead)
            if key not in merged:
                merged[key] = lead
                continue
            target = merged[key]
            target.facts.extend(fact for fact in lead.facts if fact not in target.facts)
            target.socials.extend(social for social in lead.socials if social not in target.socials)
            target.evidence.extend(lead.evidence)
            target.evidence.append(
                Evidence(
                    claim=f"Duplicate candidate merged into {target.company_name}.",
                    source_url="system://dedupe",
                    agent=self.name,
                    confidence=0.8,
                )
            )
        return list(merged.values())

    def _key_for(self, lead: LeadMemory) -> str:
        if lead.website:
            parsed = urlparse(lead.website if "://" in lead.website else f"https://{lead.website}")
            host = parsed.netloc.lower().removeprefix("www.")
            if host:
                return f"domain:{host}"

        name = re.sub(r"[^a-z0-9]+", "-", lead.company_name.lower()).strip("-")
        city = (lead.city or "").lower()
        country = (lead.country or "").lower()
        return f"name:{name}:{city}:{country}"

