from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candidate:
    action: str
    station_id: str | None
    value_kw: float
    confidence: float
    engine: str
    reason: str
