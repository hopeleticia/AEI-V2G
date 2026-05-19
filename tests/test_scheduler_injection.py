from __future__ import annotations

import pytest

from integration.coordinator import _run_lava_validator, run
from scheduling.base_scheduler import BaseScheduler


class DummyScheduler(BaseScheduler):
    def __init__(self, station_id: str | None = "station_a") -> None:
        self.station_id = station_id
        self.route_calls = 0
        self.dispatch_calls = 0
        self.routed_ev_ids: list[str] = []

    def route_ev(self, ev_feature: dict, stations: dict, grid_state: dict) -> dict:
        self.route_calls += 1
        self.routed_ev_ids.append(ev_feature["ev_id"])
        return {
            "station_id": self.station_id,
            "latency_ms": 1.5,
            "confidence": 0.9,
            "divergence": 0.0,
            "action": "route",
            "reason": "dummy route",
            "ev_id": ev_feature["ev_id"],
        }

    def dispatch_v2g(self, stations: dict, grid_state: dict) -> dict:
        self.dispatch_calls += 1
        return {
            "value_kw": 0.0,
            "latency_ms": 2.5,
            "confidence": 0.8,
            "divergence": 0.0,
            "action": "v2g",
            "reason": "dummy dispatch",
        }


class TrainableDummyScheduler(DummyScheduler):
    def __init__(self, station_id: str | None = "station_a") -> None:
        super().__init__(station_id)
        self.update_calls = 0
        self.train_calls = 0
        self.rewards: list[float] = []

    @property
    def is_trainable(self) -> bool:
        return True

    def update(self, reward: float) -> None:
        self.update_calls += 1
        self.rewards.append(reward)

    def train(self) -> float:
        self.train_calls += 1
        return 0.0


class RecordingBus:
    def __init__(self) -> None:
        self.subscriptions: list[str] = []
        self.published: list[tuple[str, dict]] = []

    def subscribe(self, topic: str, callback) -> None:
        self.subscriptions.append(topic)

    def publish(self, topic: str, payload: dict) -> None:
        self.published.append((topic, payload))


def test_injected_scheduler_routes_and_dispatches(tmp_path):
    scheduler = DummyScheduler("station_a")

    report = run(
        "config/corridor_config.yaml",
        600,
        str(tmp_path / "metrics.json"),
        str(tmp_path / "chain.jsonl"),
        scheduler,
    )

    assert scheduler.route_calls > 0
    assert scheduler.dispatch_calls == 10
    assert scheduler.routed_ev_ids
    assert report["metrics"]["decision_latency_ms_avg"] > 0.0
    assert len(report["samples"]) == 10


def test_station_id_none_uses_standalone_fallback(tmp_path):
    scheduler = DummyScheduler(station_id=None)

    report = run(
        "config/corridor_config.yaml",
        600,
        str(tmp_path / "metrics.json"),
        str(tmp_path / "chain.jsonl"),
        scheduler,
    )

    assert scheduler.route_calls > 0
    assert scheduler.dispatch_calls == 10
    assert report["metrics"]["blockchain_consensus_pct"] == 100.0


def test_trainable_dummy_updates_and_trains_in_standalone(tmp_path):
    scheduler = TrainableDummyScheduler("station_a")

    run(
        "config/corridor_config.yaml",
        600,
        str(tmp_path / "metrics.json"),
        str(tmp_path / "chain.jsonl"),
        scheduler,
    )

    assert scheduler.update_calls == 10
    assert scheduler.train_calls == 10
    assert len(scheduler.rewards) == 10
    assert all(isinstance(reward, float) for reward in scheduler.rewards)


def test_distributed_trainable_scheduler_is_rejected(tmp_path):
    scheduler = TrainableDummyScheduler()
    bus = RecordingBus()

    with pytest.raises(ValueError, match="Distributed trainable schedulers are not supported"):
        _run_lava_validator(
            "config/corridor_config.yaml",
            60,
            str(tmp_path / "metrics.json"),
            str(tmp_path / "chain.jsonl"),
            bus,
            scheduler,
        )

    assert bus.subscriptions == []
    assert bus.published == []
