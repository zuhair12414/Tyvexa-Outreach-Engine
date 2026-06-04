from __future__ import annotations

from cold_outreach_engine.models import Evidence, LeadMemory, SolutionAssessment, SolutionStatus


class ExistingSolutionAgent:
    name = "existing_solution_agent"

    TOOL_MARKERS = {
        "intercom": ("strong", "customer chat platform"),
        "hubspot": ("strong", "CRM/contact automation"),
        "zendesk": ("strong", "support desk"),
        "calendly": ("weak", "scheduler"),
        "whatsapp": ("weak", "WhatsApp/manual messaging"),
        "contact form": ("weak", "web contact form"),
        "booking": ("weak", "booking/reservation flow"),
    }

    def run(self, lead: LeadMemory) -> SolutionAssessment:
        text = " ".join(lead.facts).lower()
        detected = [tool for tool in self.TOOL_MARKERS if tool in text]
        lead.detected_tools.extend(tool for tool in detected if tool not in lead.detected_tools)

        if any(self.TOOL_MARKERS[tool][0] == "strong" for tool in detected):
            status = SolutionStatus.STRONG_SOLUTION
        elif detected:
            status = SolutionStatus.WEAK_SOLUTION
        elif lead.website:
            status = SolutionStatus.UNKNOWN
        else:
            status = SolutionStatus.UNKNOWN

        evidence = Evidence(
            claim=f"Detected public solution markers: {', '.join(detected) or 'none visible'}",
            source_url=lead.website or "system://no-website",
            agent=self.name,
            confidence=0.55 if detected else 0.35,
        )
        lead.evidence.append(evidence)

        solution_types = [self.TOOL_MARKERS[tool][1] for tool in detected]
        if status == SolutionStatus.STRONG_SOLUTION:
            implication = "Visible mature support/CRM tooling; deprioritize unless another gap is strong."
        elif status == SolutionStatus.WEAK_SOLUTION:
            implication = "Visible manual or partial intake flow; pitch voice AI as missed-call/support leakage capture."
        else:
            implication = "No public solution marker detected; classify as unknown, not confirmed no-solution."

        return SolutionAssessment(
            lead_id=lead.id,
            status=status,
            solution_type=", ".join(solution_types) if solution_types else "unknown",
            detected_tools=detected,
            outreach_implication=implication,
            evidence_ids=[evidence.id],
        )
