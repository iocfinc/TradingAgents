from __future__ import annotations

import json
from pathlib import Path

from tradingagents.thesis_program.schemas import SeedPackage


def load_seed_package(path: str | Path) -> SeedPackage:
    seed_path = Path(path)
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    return SeedPackage.model_validate(payload)
