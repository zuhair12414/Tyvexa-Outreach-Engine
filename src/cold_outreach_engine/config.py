from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    max_candidates_per_run: int
    max_deep_analysis_per_run: int
    openai_api_key: str | None
    google_places_api_key: str | None
    brave_search_api_key: str | None
    firecrawl_api_key: str | None
    hunter_api_key: str | None


def _load_local_env() -> None:
    env_path = Path(".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def load_settings() -> Settings:
    _load_local_env()
    data_dir = Path(os.getenv("LEADGEN_DATA_DIR", "./data")).resolve()
    return Settings(
        data_dir=data_dir,
        max_candidates_per_run=int(os.getenv("LEADGEN_MAX_CANDIDATES_PER_RUN", "50")),
        max_deep_analysis_per_run=int(os.getenv("LEADGEN_MAX_DEEP_ANALYSIS_PER_RUN", "20")),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        google_places_api_key=os.getenv("GOOGLE_PLACES_API_KEY") or None,
        brave_search_api_key=os.getenv("BRAVE_SEARCH_API_KEY") or None,
        firecrawl_api_key=os.getenv("FIRECRAWL_API_KEY") or None,
        hunter_api_key=os.getenv("HUNTER_API_KEY") or None,
    )
