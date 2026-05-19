from __future__ import annotations

from statistics import median

from lava.candidates import Candidate


class MedianEnsemble:
    def __init__(self, min_confidence: float, max_divergence: float) -> None:
        self.min_confidence = min_confidence
        self.max_divergence = max_divergence
        self.previous_by_action: dict[str, dict] = {}

    def combine_route(self, candidates: list[Candidate]) -> dict:
        confidence = median([c.confidence for c in candidates])
        votes: dict[str, float] = {}
        for candidate in candidates:
            if candidate.station_id:
                votes[candidate.station_id] = votes.get(candidate.station_id, 0.0) + candidate.confidence
        if not votes:
            # Fallback: pick station_id from the highest-confidence candidate that has one
            best = max((c for c in candidates if c.station_id is not None), key=lambda c: c.confidence, default=None)
            station_id = best.station_id if best else None
            disagreement = 1.0
        else:
            station_id = max(votes, key=votes.get)
            disagreement = 1.0 - votes[station_id] / max(0.01, sum(votes.values()))
        return self._finalize("route", station_id, 0.0, confidence, disagreement, candidates)

    def combine_v2g(self, candidates: list[Candidate]) -> dict:
        values = [candidate.value_kw for candidate in candidates]
        value = median(values)
        confidence = median([c.confidence for c in candidates])
        divergence = (max(values) - min(values)) / max(1.0, max(values))
        return self._finalize("v2g", None, value, confidence, divergence, candidates)

    def _finalize(self, action: str, station_id: str | None, value_kw: float, confidence: float, divergence: float, candidates: list[Candidate]) -> dict:
        deferred = confidence < self.min_confidence or divergence > self.max_divergence
        previous = self.previous_by_action.get(action)
        if deferred and previous:
            decision = dict(previous)
            decision["deferred"] = True
            decision["reason"] = "cooldown retained previous decision"
        else:
            decision = {
                "action": action,
                "station_id": station_id,
                "value_kw": round(value_kw, 3),
                "confidence": round(confidence, 3),
                "divergence": round(divergence, 3),
                "deferred": deferred,
                "reason": "median ensemble accepted" if not deferred else "deferred by cooldown gate",
            }
            if not deferred:
                self.previous_by_action[action] = dict(decision)
        decision["trace"] = [candidate.__dict__ for candidate in candidates]
        return decision
