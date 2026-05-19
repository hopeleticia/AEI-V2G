from __future__ import annotations

import argparse
import json
import os
import threading
import time
from pathlib import Path

from integration.ev_router import nearest_station
from integration.metrics import summarize
from integration.v2g_dispatcher import apply_v2g
from logging_layer.decision_log import DecisionLog
from scheduling.base_scheduler import BaseScheduler
from scheduling.lava_scheduler import LAVAScheduler
from sim.corridor import Corridor
from sim.entities import EV
from sim.station_model import receive_ev, update_station

_NODE_ROLE   = os.environ.get("AEI_NODE_ROLE", "standalone")
_NODE_ID     = os.environ.get("AEI_NODE_ID", "standalone")
_MQTT_BROKER = os.environ.get("AEI_MQTT_BROKER", "192.168.137.217")
_GRID_START_MINUTE = int(os.environ.get("AEI_GRID_START_MINUTE", "0"))


def _reserve_prearrival_slot(station, ev_id: str, feature: dict, tick: int | float) -> dict:
    eta_by_station = feature.get("eta_by_station_min") or {}
    eta_min = float(eta_by_station.get(station.id, 0.0))
    ttl_min = max(30.0, eta_min + 10.0)
    return station.reserve_slot(ev_id, eta_min, tick, ttl_min=ttl_min)


def _default_scheduler(config_path: str) -> BaseScheduler:
    """Build the default LAVAScheduler.  Called when no scheduler is injected."""
    return LAVAScheduler.from_yaml(
        "config/lava_weights.yaml", "config/rules.yaml", "config/constraints.yaml"
    )


def run(
    config_path: str,
    duration: int,
    output_path: str | None = None,
    chain_path: str = "data/chain.jsonl",
    scheduler: BaseScheduler | None = None,
) -> dict:
    """Entry point.  Pass a *scheduler* instance to swap out LAVA for DRL."""
    if _NODE_ROLE not in ("standalone", ""):
        try:
            from integration.node_comms import NodeBus
            bus = NodeBus(_NODE_ID, _MQTT_BROKER)
        except Exception as exc:
            print(f"[{_NODE_ID}] MQTT unavailable ({exc}), falling back to standalone")
        else:
            try:
                if _NODE_ROLE == "lava-validator":
                    return _run_lava_validator(config_path, duration, output_path, chain_path, bus, scheduler)
                if _NODE_ROLE == "station-validator":
                    return _run_station_validator(config_path, duration, output_path, chain_path, bus)
                if _NODE_ROLE == "rsu-observer":
                    return _run_rsu_observer(config_path, duration, output_path, chain_path, bus)
                if _NODE_ROLE == "grid-observer":
                    return _run_grid_observer(config_path, duration, output_path, chain_path, bus)
            finally:
                bus.stop()
    return _run_standalone(config_path, duration, output_path, chain_path, scheduler)


def _run_standalone(
    config_path: str,
    duration: int,
    output_path: str | None,
    chain_path: str,
    scheduler: BaseScheduler | None = None,
) -> dict:
    corridor = Corridor.from_yaml(config_path)
    if scheduler is None:
        scheduler = _default_scheduler(config_path)
    log = DecisionLog(chain_path)
    active_evs = []
    completed = 0
    samples: list[dict] = []
    tick_minutes = corridor.tick_seconds / 60.0
    previous_actual_kw = 0.0
    v2g_credits_total = 0
    credit_ledger_transactions = 0
    credit_ledger_failures = 0

    for minute in range(0, duration // 60):
        active_evs.extend(corridor.generator.spawn(tick_minutes, corridor.length_km))
        for station in corridor.stations.values():
            done = update_station(station, tick_minutes, tick=minute)
            completed += len(done)
            for ev in done:
                log.append("ev_completed", {
                    "ev_id": ev.id, "station_id": ev.assigned_station,
                    "final_soc": ev.battery_pct, "SoH_k": ev.SoH_k,
                    "SoC_req_k": ev.SoC_req_k, "T_dep_k": ev.T_dep_k,
                    "soc_trajectory": ev.soc_trajectory,
                })

        for ev in active_evs:
            ev.advance(tick_minutes)

        total_load = sum(station.current_load_kw for station in corridor.stations.values())
        grid_state = corridor.grid.state(minute, total_load)
        sensed = corridor.sense(active_evs)
        routed_now = 0
        latency_values: list[float] = []
        baseline_wait = 0.0
        lava_wait = 0.0

        for feature in sensed:
            ev = next((candidate for candidate in active_evs if candidate.id == feature["ev_id"]), None)
            if not ev or ev.assigned_station:
                continue
            decision = scheduler.route_ev(feature, corridor.stations, grid_state)
            station_id = decision["station_id"] or nearest_station(ev, corridor.stations)
            ev.assigned_station = station_id
            reservation = _reserve_prearrival_slot(corridor.stations[station_id], ev.id, feature, minute)
            decision["reservation"] = reservation
            log.append("route", decision)
            log.append("slot_reserved", reservation)
            routed_now += 1
            latency_values.append(decision["latency_ms"])
            lava_wait += corridor.stations[station_id].estimated_wait_minutes()
            baseline_id = nearest_station(ev, corridor.stations)
            baseline_wait += corridor.stations[baseline_id].estimated_wait_minutes() + max(0.0, corridor.stations[baseline_id].utilization - 0.75) * 18.0

        arrived = [ev for ev in active_evs if ev.assigned_station and ev.km >= corridor.stations[ev.assigned_station].km]
        arrived_ids = {ev.id for ev in arrived}
        for ev in arrived:
            receive_ev(corridor.stations[ev.assigned_station], ev)
        active_evs = [ev for ev in active_evs if ev.id not in arrived_ids]

        v2g_decision = scheduler.dispatch_v2g(corridor.stations, grid_state)
        log.append("v2g_dispatch", v2g_decision)
        v2g = apply_v2g(corridor.stations, v2g_decision["value_kw"], tick_minutes, grid_state["v2g_buy_price"], tick=minute)
        v2g_credits_total += v2g.get("credits_awarded", 0)
        credit_ledger_transactions += v2g.get("credit_ledger_transactions", 0)
        credit_ledger_failures += v2g.get("credit_ledger_failures", 0)
        for settlement in v2g.get("settlements", []):
            log.append("v2g_settlement", {**settlement, "tick": minute})
        relieved_grid = corridor.grid.state(minute, total_load, v2g_decision["value_kw"])

        # ── Per-tick reward signal (Section 5.5, context doc) ──────────────
        # Passed to DRL schedulers via update(); is a no-op for LAVA.
        if scheduler.is_trainable:
            max_station_kw = max(s.max_kw for s in corridor.stations.values())
            par_penalty    = -0.4 * min(1.0, total_load / max(1.0, max_station_kw))
            tec_penalty    = -0.3 * (total_load * grid_state["tariff"] * tick_minutes / 60.0) / 500.0
            v2g_reward     = +0.2 * v2g["revenue"]
            stress_relief  = +0.1 * (1.0 - relieved_grid["stress"])
            tick_reward    = par_penalty + tec_penalty + v2g_reward + stress_relief
            scheduler.update(tick_reward)
            scheduler.train()

        forecast_kw = previous_actual_kw * 0.65 + total_load * 0.35
        previous_actual_kw = total_load
        baseline_grid_state = corridor.grid.state(minute, total_load * 1.18)
        samples.append(
            {
                "minute": minute,
                "evs_served": completed,
                "lava_wait_min": lava_wait / max(1, routed_now),
                "baseline_wait_min": baseline_wait / max(1, routed_now),
                "grid_stress": relieved_grid["stress"],
                "baseline_grid_stress": baseline_grid_state["stress"],
                "latency_ms": sum(latency_values) / len(latency_values) if latency_values else v2g_decision["latency_ms"],
                "forecast_kw": forecast_kw,
                "actual_kw": total_load,
                "v2g_invited": v2g["invited"],
                "v2g_accepted": v2g["accepted"],
                "v2g_revenue": v2g["revenue"],
                "v2g_credits_awarded": v2g.get("credits_awarded", 0),
                "credit_ledger_transactions": v2g.get("credit_ledger_transactions", 0),
            }
        )

    metrics = summarize(samples)
    report = {
        "duration_seconds": duration,
        "metrics": metrics,
        "samples": samples[-10:],
        "full_samples": samples,
        "sample_count": len(samples),
        "v2g_credits_awarded": v2g_credits_total,
        "credit_ledger_transactions": credit_ledger_transactions,
        "credit_ledger_failures": credit_ledger_failures,
    }
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
    return report


# ── Role: rsu-observer (pi5) ────────────────────────────────────────────────

def _run_rsu_observer(
    config_path: str, duration: int, output_path: str | None, chain_path: str, bus
) -> dict:
    """pi5 — EV generator + RSU sensing.  Publishes features to aei/rsu/sense."""
    from integration.node_comms import TOPIC_RSU_SENSE, TOPIC_CHAIN_SYNC

    corridor = Corridor.from_yaml(config_path)
    log_chain = DecisionLog(chain_path)
    tick_minutes = corridor.tick_seconds / 60.0
    tick_secs = corridor.tick_seconds
    ticks = duration // tick_secs
    active_evs: list = []
    sense_count = 0

    for tick in range(ticks):
        t0 = time.monotonic()
        active_evs.extend(corridor.generator.spawn(tick_minutes, corridor.length_km))
        for ev in active_evs:
            ev.advance(tick_minutes)
        features = corridor.sense(active_evs)
        for feat in features:
            bus.publish(TOPIC_RSU_SENSE, feat)
            sense_count += 1
        # Remove EVs that have exited the corridor
        active_evs = [ev for ev in active_evs if ev.km < corridor.length_km]
        rec = log_chain.append("rsu_sense_batch", {"count": len(features), "tick": tick})
        bus.publish(TOPIC_CHAIN_SYNC, {"node": _NODE_ID, "hash": rec["hash"], "tick": tick})
        _pace(t0, tick_secs)

    report = {"node": _NODE_ID, "role": "rsu-observer", "sense_count": sense_count, "ticks": ticks}
    _save(report, output_path)
    return report


# ── Role: grid-observer (pi6) ───────────────────────────────────────────────

def _run_grid_observer(
    config_path: str, duration: int, output_path: str | None, chain_path: str, bus
) -> dict:
    """pi6 — CAISO grid model.  Subscribes to station loads, publishes grid state."""
    from integration.node_comms import TOPIC_STATION_STATE, TOPIC_GRID_STATE, TOPIC_CHAIN_SYNC

    corridor = Corridor.from_yaml(config_path)
    log_chain = DecisionLog(chain_path)
    tick_secs = corridor.tick_seconds
    ticks = duration // tick_secs
    _lock = threading.Lock()
    total_station_load_kw = 0.0

    def on_station_state(payload: dict) -> None:
        nonlocal total_station_load_kw
        with _lock:
            total_station_load_kw = payload.get("total_load_kw", 0.0)

    bus.subscribe(TOPIC_STATION_STATE, on_station_state)
    samples: list[dict] = []

    for minute in range(ticks):
        t0 = time.monotonic()
        with _lock:
            load = total_station_load_kw
        profile_minute = _GRID_START_MINUTE + minute
        gs = corridor.grid.state(profile_minute, load)
        gs["minute"] = minute
        gs["profile_minute"] = profile_minute
        gs["node"] = _NODE_ID
        bus.publish(TOPIC_GRID_STATE, gs)
        rec = log_chain.append("grid_state", gs)
        bus.publish(TOPIC_CHAIN_SYNC, {"node": _NODE_ID, "hash": rec["hash"], "tick": minute})
        samples.append(gs)
        _pace(t0, tick_secs)

    report = {
        "node": _NODE_ID,
        "role": "grid-observer",
        "avg_stress": round(sum(s["stress"] for s in samples) / max(1, len(samples)), 4),
        "ticks": ticks,
    }
    _save(report, output_path)
    return report


# ── Role: station-validator (pi2, pi3) ──────────────────────────────────────

def _run_station_validator(
    config_path: str, duration: int, output_path: str | None, chain_path: str, bus
) -> dict:
    """pi2/pi3 — Station simulation.  Publishes state; applies LAVA routing + V2G."""
    from integration.node_comms import (
        TOPIC_STATION_STATE, TOPIC_LAVA_ROUTE, TOPIC_LAVA_V2G, TOPIC_CHAIN_SYNC,
    )

    corridor = Corridor.from_yaml(config_path)
    log_chain = DecisionLog(chain_path)
    tick_minutes = corridor.tick_seconds / 60.0
    tick_secs = corridor.tick_seconds
    ticks = duration // tick_secs
    _lock = threading.Lock()
    routing_decisions: list[dict] = []
    v2g_decisions: list[dict] = []
    scheduled_arrivals: list[dict] = []
    seen_routes: set[str] = set()

    def on_route(payload: dict) -> None:
        with _lock:
            routing_decisions.append(payload)

    def on_v2g(payload: dict) -> None:
        with _lock:
            v2g_decisions.append(payload)

    bus.subscribe(TOPIC_LAVA_ROUTE, on_route)
    bus.subscribe(TOPIC_LAVA_V2G, on_v2g)

    # Which stations does this node own?  Comma-separated env var, or all.
    station_ids_env = os.environ.get("AEI_STATION_IDS", "")
    my_station_ids = set(station_ids_env.split(",")) if station_ids_env else set(corridor.stations.keys())
    my_stations = {k: v for k, v in corridor.stations.items() if k in my_station_ids}

    completed = 0
    arrivals = 0
    routes_received = 0
    v2g_revenue_total = 0.0
    v2g_credits_total = 0
    credit_ledger_transactions = 0
    credit_ledger_failures = 0

    for tick in range(ticks):
        t0 = time.monotonic()
        for arrival in list(scheduled_arrivals):
            arrival["eta_remaining_min"] -= tick_minutes
            if arrival["eta_remaining_min"] <= 0:
                station = my_stations.get(arrival["station_id"])
                if station is not None:
                    receive_ev(station, arrival["ev"])
                    arrivals += 1
                scheduled_arrivals.remove(arrival)

        for station in my_stations.values():
            done = update_station(station, tick_minutes, tick=tick)
            completed += len(done)
            for ev in done:
                log_chain.append("ev_completed", {
                    "ev_id": ev.id, "station_id": ev.assigned_station,
                    "final_soc": round(ev.battery_pct, 2), "SoH_k": ev.SoH_k,
                    "SoC_req_k": ev.SoC_req_k, "T_dep_k": ev.T_dep_k,
                    "soc_trajectory": ev.soc_trajectory,
                })

        with _lock:
            pending_routes = routing_decisions[:]
            routing_decisions.clear()
            pending_v2g = v2g_decisions[:]
            v2g_decisions.clear()

        for dec in pending_routes:
            station_id = dec.get("station_id")
            ev_id = dec.get("ev_id")
            if station_id in my_stations:
                routes_received += 1
                log_chain.append("route_applied", dec)
                if ev_id and ev_id not in seen_routes:
                    seen_routes.add(ev_id)
                    feature = dec.get("ev_feature") or {}
                    battery = float(feature.get("battery_pct", 50.0))
                    soh = float(feature.get("SoH_k", 1.0))
                    soc_req = float(feature.get("SoC_req_k", 80.0))
                    required_kwh = float(feature.get("required_kwh", max(8.0, (soc_req - battery) * soh * 0.72)))
                    ev = EV(
                        id=str(ev_id),
                        km=float(feature.get("km", my_stations[station_id].km)),
                        speed_kmh=float(feature.get("speed_kmh", 80.0)),
                        battery_pct=battery,
                        destination_km=corridor.length_km,
                        charge_request=True,
                        required_kwh=required_kwh,
                        assigned_station=station_id,
                        v2g_eligible=bool(feature.get("v2g_eligible", battery >= 55.0)),
                        SoH_k=soh,
                        SoC_req_k=soc_req,
                        T_dep_k=float(feature.get("T_dep_k", 60.0)),
                    )
                    eta_by_station = feature.get("eta_by_station_min") or {}
                    eta = float(eta_by_station.get(station_id, 0.0))
                    reservation = my_stations[station_id].reserve_slot(str(ev_id), eta, tick, ttl_min=max(30.0, eta + 10.0))
                    log_chain.append("slot_reserved", reservation)
                    scheduled_arrivals.append({
                        "station_id": station_id,
                        "ev": ev,
                        "eta_remaining_min": eta,
                    })

        for dec in pending_v2g:
            v2g_kw = float(dec.get("value_kw", 0.0))
            buy_price = float(dec.get("buy_price", 0.42))
            v2g = apply_v2g(my_stations, v2g_kw, tick_minutes, buy_price, tick=tick)
            v2g_revenue_total += v2g["revenue"]
            v2g_credits_total += v2g.get("credits_awarded", 0)
            credit_ledger_transactions += v2g.get("credit_ledger_transactions", 0)
            credit_ledger_failures += v2g.get("credit_ledger_failures", 0)
            log_chain.append("v2g_applied", {**dec, "result": v2g})
            for settlement in v2g.get("settlements", []):
                log_chain.append("v2g_settlement", {**settlement, "tick": tick})

        total_load = sum(s.current_load_kw for s in my_stations.values())
        state = {
            "node": _NODE_ID,
            "tick": tick,
            "total_load_kw": total_load,
            "stations": {
                sid: {
                    "load_kw": s.current_load_kw,
                    "available_slots": s.available_slots,
                    "queue_depth": s.queue_depth,
                    "utilization": s.utilization,
                    "reservations": list(s.reservations.values()),
                    "active_evs": [
                        {
                            "id": ev.id,
                            "battery_pct": ev.battery_pct,
                            "required_kwh": ev.required_kwh,
                            "v2g_eligible": ev.v2g_eligible,
                            "SoH_k": ev.SoH_k,
                            "SoC_req_k": ev.SoC_req_k,
                            "T_dep_k": ev.T_dep_k,
                            "soc_trajectory": ev.soc_trajectory,
                        }
                        for ev in s.active_evs
                    ],
                    "queue_evs": [
                        {
                            "id": ev.id,
                            "battery_pct": ev.battery_pct,
                            "required_kwh": ev.required_kwh,
                            "v2g_eligible": ev.v2g_eligible,
                            "SoH_k": ev.SoH_k,
                            "SoC_req_k": ev.SoC_req_k,
                            "T_dep_k": ev.T_dep_k,
                            "soc_trajectory": ev.soc_trajectory,
                        }
                        for ev in s.queue
                    ],
                }
                for sid, s in my_stations.items()
            },
        }
        bus.publish(TOPIC_STATION_STATE, state)
        rec = log_chain.append("station_state", state)
        bus.publish(TOPIC_CHAIN_SYNC, {"node": _NODE_ID, "hash": rec["hash"], "tick": tick})
        _pace(t0, tick_secs)

    report = {
        "node": _NODE_ID,
        "role": "station-validator",
        "evs_served": completed,
        "evs_arrived": arrivals,
        "routes_received": routes_received,
        "active_or_queued_evs": sum(len(s.active_evs) + len(s.queue) for s in my_stations.values()),
        "v2g_revenue": round(v2g_revenue_total, 2),
        "v2g_credits_awarded": v2g_credits_total,
        "credit_ledger_transactions": credit_ledger_transactions,
        "credit_ledger_failures": credit_ledger_failures,
        "stations": sorted(my_station_ids),
        "ticks": ticks,
    }
    _save(report, output_path)
    return report


# ── Role: lava-validator (pi1) ──────────────────────────────────────────────

def _run_lava_validator(
    config_path: str, duration: int, output_path: str | None, chain_path: str, bus,
    scheduler: BaseScheduler | None = None,
) -> dict:
    """pi1 — Decision engine.  Subscribes to sense/station/grid; publishes decisions."""
    from integration.node_comms import (
        TOPIC_RSU_SENSE, TOPIC_STATION_STATE, TOPIC_GRID_STATE,
        TOPIC_LAVA_ROUTE, TOPIC_LAVA_V2G, TOPIC_CHAIN_SYNC,
    )

    corridor = Corridor.from_yaml(config_path)
    if scheduler is None:
        scheduler = _default_scheduler(config_path)
    if scheduler.is_trainable:
        message = (
            "Distributed trainable schedulers are not supported by lava-validator; "
            "run trainable schedulers in standalone mode until distributed reward plumbing is implemented."
        )
        print(f"[{_NODE_ID}] {message}")
        raise ValueError(message)
    log_chain = DecisionLog(chain_path)
    tick_secs = corridor.tick_seconds
    ticks = duration // tick_secs
    _lock = threading.Lock()

    pending_features: list[dict] = []
    grid_state: dict = corridor.grid.state(0, 0.0)
    routed_ev_ids: set[str] = set()

    def on_sense(payload: dict) -> None:
        with _lock:
            pending_features.append(payload)

    def on_station_state(payload: dict) -> None:
        stations = payload.get("stations", {})
        with _lock:
            for sid, state in stations.items():
                station = corridor.stations.get(sid)
                if station is None:
                    continue
                station.active_evs = [
                    EV(
                        id=str(row.get("id", f"{sid}_active")),
                        km=station.km,
                        speed_kmh=0.0,
                        battery_pct=float(row.get("battery_pct", 50.0)),
                        destination_km=corridor.length_km,
                        charge_request=True,
                        required_kwh=float(row.get("required_kwh", 8.0)),
                        assigned_station=sid,
                        v2g_eligible=bool(row.get("v2g_eligible", False)),
                        SoH_k=float(row.get("SoH_k", 1.0)),
                        SoC_req_k=float(row.get("SoC_req_k", 80.0)),
                        T_dep_k=float(row.get("T_dep_k", 60.0)),
                        soc_trajectory=list(row.get("soc_trajectory", [])),
                    )
                    for row in state.get("active_evs", [])
                ]
                station.queue = [
                    EV(
                        id=str(row.get("id", f"{sid}_queue")),
                        km=station.km,
                        speed_kmh=0.0,
                        battery_pct=float(row.get("battery_pct", 50.0)),
                        destination_km=corridor.length_km,
                        charge_request=True,
                        required_kwh=float(row.get("required_kwh", 8.0)),
                        assigned_station=sid,
                        v2g_eligible=bool(row.get("v2g_eligible", False)),
                        SoH_k=float(row.get("SoH_k", 1.0)),
                        SoC_req_k=float(row.get("SoC_req_k", 80.0)),
                        T_dep_k=float(row.get("T_dep_k", 60.0)),
                        soc_trajectory=list(row.get("soc_trajectory", [])),
                    )
                    for row in state.get("queue_evs", [])
                ]
                station.reservations = {
                    str(row.get("ev_id")): dict(row)
                    for row in state.get("reservations", [])
                    if row.get("ev_id")
                }

    def on_grid_state(payload: dict) -> None:
        nonlocal grid_state
        with _lock:
            grid_state = payload

    bus.subscribe(TOPIC_RSU_SENSE, on_sense)
    bus.subscribe(TOPIC_STATION_STATE, on_station_state)
    bus.subscribe(TOPIC_GRID_STATE, on_grid_state)

    samples: list[dict] = []
    routed_total = 0
    all_latencies: list[float] = []

    for tick in range(ticks):
        t0 = time.monotonic()

        with _lock:
            features = pending_features[:]
            pending_features.clear()
            cur_grid = dict(grid_state)

        routed_now = 0
        tick_latencies: list[float] = []

        for feat in features:
            ev_id = feat.get("ev_id")
            if ev_id in routed_ev_ids:
                continue
            decision = scheduler.route_ev(feat, corridor.stations, cur_grid)
            battery = float(feat.get("battery_pct", 50.0))
            soh = float(feat.get("SoH_k", 1.0))
            soc_req = float(feat.get("SoC_req_k", 80.0))
            decision["ev_feature"] = {
                **feat,
                "required_kwh": max(8.0, (soc_req - battery) * soh * 0.72),
                "v2g_eligible": battery >= 55.0,
            }
            station_id = decision.get("station_id")
            if station_id in corridor.stations:
                reservation = _reserve_prearrival_slot(corridor.stations[station_id], str(ev_id), feat, tick)
                decision["reservation"] = reservation
            rec = log_chain.append("route", decision)
            decision["chain_hash"] = rec["hash"]
            bus.publish(TOPIC_LAVA_ROUTE, decision)
            bus.publish(TOPIC_CHAIN_SYNC, {"node": _NODE_ID, "hash": rec["hash"], "tick": tick})
            routed_ev_ids.add(ev_id)
            routed_now += 1
            tick_latencies.append(decision["latency_ms"])
            routed_total += 1

        v2g_decision = scheduler.dispatch_v2g(corridor.stations, cur_grid)
        rec = log_chain.append("v2g_dispatch", v2g_decision)
        v2g_pub = {
            **v2g_decision,
            "buy_price": cur_grid.get("v2g_buy_price", 0.42),
            "chain_hash": rec["hash"],
        }
        bus.publish(TOPIC_LAVA_V2G, v2g_pub)
        all_latencies.extend(tick_latencies)

        samples.append({
            "tick": tick,
            "routed": routed_now,
            "latency_ms": (sum(tick_latencies) / len(tick_latencies)) if tick_latencies else v2g_decision["latency_ms"],
            "v2g_kw": v2g_decision["value_kw"],
            "grid_stress": cur_grid.get("stress", 0.0),
        })
        _pace(t0, tick_secs)

    report = {
        "node": _NODE_ID,
        "role": "lava-validator",
        "evs_routed": routed_total,
        "decision_latency_ms_avg": round(sum(all_latencies) / max(1, len(all_latencies)), 3),
        "ticks": ticks,
        "samples": samples[-10:],
        "full_samples": samples,
        "sample_count": len(samples),
    }
    _save(report, output_path)
    return report


# ── Helpers ─────────────────────────────────────────────────────────────────

def _pace(t0: float, tick_secs: int) -> None:
    """Sleep for the remainder of a tick window so real-time pacing is maintained."""
    remaining = tick_secs - (time.monotonic() - t0)
    if remaining > 0:
        time.sleep(remaining)


def _save(report: dict, output_path: str | None) -> None:
    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/corridor_config.yaml")
    parser.add_argument("--duration", type=int, default=3600)
    parser.add_argument("--output", default="reports/latest_metrics.json")
    parser.add_argument("--chain", default="data/chain.jsonl")
    args = parser.parse_args()
    report = run(args.config, args.duration, args.output, args.chain)
    print(json.dumps(report.get("metrics", report), indent=2))


if __name__ == "__main__":
    main()
