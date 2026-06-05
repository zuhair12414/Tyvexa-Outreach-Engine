from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def read_collection(self, name: str) -> list[dict[str, Any]]:
        path = self.data_dir / f"{name}.json"
        if not path.exists():
            return []
        return json.loads(path.read_text())

    def write_collection(self, name: str, rows: list[dict[str, Any]]) -> None:
        path = self.data_dir / f"{name}.json"
        path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")

    def append(self, name: str, row: dict[str, Any]) -> None:
        rows = self.read_collection(name)
        rows.append(row)
        self.write_collection(name, rows)

    def upsert(self, name: str, row: dict[str, Any], key: str = "id") -> None:
        rows = self.read_collection(name)
        for index, existing in enumerate(rows):
            if existing.get(key) == row.get(key):
                rows[index] = row
                self.write_collection(name, rows)
                return
        rows.append(row)
        self.write_collection(name, rows)

    def append_artifact(self, row: dict[str, Any]) -> None:
        self.append("agent_artifacts", row)

    def append_agent_step(self, row: dict[str, Any]) -> None:
        self.append("agent_steps", row)

    def read_artifacts(
        self,
        run_id: str | None = None,
        campaign_id: str | None = None,
        lead_id: str | None = None,
        agent_name: str | None = None,
        artifact_type: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.read_collection("agent_artifacts")
        return [
            row
            for row in rows
            if self._matches(row, "run_id", run_id)
            and self._matches(row, "campaign_id", campaign_id)
            and self._matches(row, "lead_id", lead_id)
            and self._matches(row, "producer_agent", agent_name)
            and self._matches(row, "artifact_type", artifact_type)
        ]

    def read_agent_steps(
        self,
        run_id: str | None = None,
        campaign_id: str | None = None,
        lead_id: str | None = None,
        agent_name: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = self.read_collection("agent_steps")
        return [
            row
            for row in rows
            if self._matches(row, "run_id", run_id)
            and self._matches(row, "campaign_id", campaign_id)
            and self._matches(row, "lead_id", lead_id)
            and self._matches(row, "agent_name", agent_name)
        ]

    def _matches(self, row: dict[str, Any], key: str, expected: str | None) -> bool:
        return expected is None or row.get(key) == expected
