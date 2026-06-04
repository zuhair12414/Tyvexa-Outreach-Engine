from __future__ import annotations

import json
from typing import Any

import httpx


class OpenAILlmProvider:
    endpoint = "https://api.openai.com/v1/responses"

    def __init__(self, api_key: str, model: str) -> None:
        self.api_key = api_key
        self.model = model

    def classify(self, task: str, payload: dict) -> dict:
        if task != "campaign_strategy":
            raise ValueError(f"Unsupported LLM task: {task}")

        body = {
            "model": self.model,
            "input": [
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": self._system_prompt(),
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(payload, sort_keys=True),
                        }
                    ],
                },
            ],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "campaign_strategy",
                    "strict": True,
                    "schema": self._campaign_strategy_schema(),
                }
            },
        }

        with httpx.Client(timeout=45) as client:
            response = client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            text = self._extract_text(data)
            if not text:
                raise ValueError("OpenAI response did not include structured text output.")
            parsed = json.loads(text)
            parsed["_model"] = self.model
            return parsed

    def _system_prompt(self) -> str:
        return (
            "You are the Campaign Strategy Agent for a lead generation engine. "
            "Convert the user's prompt into a precise lead-generation operating spec. "
            "Do not invent factual lead data. Infer campaign intent, geography, target "
            "buyer segment, missing-solution constraints, evidence requirements, source "
            "strategy, search queries, reject rules, and scoring weights. Return only "
            "schema-valid JSON."
        )

    def _extract_text(self, data: dict[str, Any]) -> str | None:
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        for output in data.get("output", []):
            for content in output.get("content", []):
                if isinstance(content.get("text"), str):
                    return content["text"]
        return None

    def _campaign_strategy_schema(self) -> dict:
        string_array = {"type": "array", "items": {"type": "string"}}
        return {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "offer": {"type": "string"},
                "countries": string_array,
                "target_locations": string_array,
                "target_industries": string_array,
                "pain_hypotheses": string_array,
                "solution_gaps": string_array,
                "good_lead_traits": string_array,
                "reject_rules": string_array,
                "source_priorities": string_array,
                "search_queries": string_array,
                "evidence_requirements": string_array,
                "buyer_personas": string_array,
                "scoring_rubric": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "icp_fit": {"type": "integer"},
                        "public_evidence": {"type": "integer"},
                        "contactability": {"type": "integer"},
                        "pain_signal": {"type": "integer"},
                        "solution_gap": {"type": "integer"},
                        "trust": {"type": "integer"},
                    },
                    "required": [
                        "icp_fit",
                        "public_evidence",
                        "contactability",
                        "pain_signal",
                        "solution_gap",
                        "trust",
                    ],
                },
                "clarification_triggers": string_array,
                "confidence_notes": string_array,
            },
            "required": [
                "offer",
                "countries",
                "target_locations",
                "target_industries",
                "pain_hypotheses",
                "solution_gaps",
                "good_lead_traits",
                "reject_rules",
                "source_priorities",
                "search_queries",
                "evidence_requirements",
                "buyer_personas",
                "scoring_rubric",
                "clarification_triggers",
                "confidence_notes",
            ],
        }
