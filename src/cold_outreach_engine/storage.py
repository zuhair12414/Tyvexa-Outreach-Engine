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

