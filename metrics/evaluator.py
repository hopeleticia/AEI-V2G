from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from statistics import mean
from typing import Any

DEFAULT_REWARD_WEIGHTS = {
    "par": 0.4,
    "tec": 0.3,
    "degradation": 0.1,
    "soc_satisfaction": 0.2,
}

DEFAULT_TICK_MINUTES = 1.0
DEFAULT_TARIFF = 0.35
DEFAULT_BATTERY_KWH = 72.0
DEFAULT_DEGRADATION_RATE = 0.0025


def evaluate_episode(
    episode: Mapping[str, Any] | Sequence[Mapping[str, Any]] | str | Path,
    *,
    tick_minutes: float | None = None,
    default_tariff: float = DEFAULT_TARIFF,
    degradation_rate: float = DEFAULT_DEGRADATION_RATE,
    battery_kwh: float = DEFAULT_BATTERY_KWH,
    reward_weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    """Compute the Obj-9 paper metrics from episode or JSONL-like data.

    The evaluator accepts coordinator reports, lists of decision-chain records,
    JSON/JSONL paths, or synthetic dictionaries with ``samples``, ``events``,
    ``ev_sessions`` and/or ``records`` keys. It never writes to or mutates the
    source object, which keeps existing research artifacts safe.
    """
    data = _load_episode(episode)
    samples = _samples(data)
    records = _records(data)
    sessions = _sessions(data, records)
    inferred_tick_minutes = tick_minutes or _infer_tick_minutes(samples) or DEFAULT_TICK_MINUTES

    par = peak_to_average_ratio(samples)
    tec = total_energy_cost(samples, tick_minutes=inferred_tick_minutes, default_tariff=default_tariff)
    satisfaction = soc_satisfaction(sessions, population=_ev_population(data, records, sessions))
    lag = scheduling_lag(records, samples=samples)
    degradation = battery_degradation_cost(
        sessions,
        tick_minutes=inferred_tick_minutes,
        degradation_rate=degradation_rate,
        battery_kwh=battery_kwh,
    )
    reward = episode_reward(
        par=par["par"],
        tec=tec["tec"],
        degradation_cost=degradation["degradation_cost"],
        soc_satisfaction_ratio=satisfaction["soc_satisfaction_ratio"],
        weights=reward_weights,
    )

    return {
        "par": par,
        "tec": tec,
        "soc_satisfaction": satisfaction,
        "scheduling_lag": lag,
        "battery_degradation": degradation,
        "sensing_gain_inputs": {
            "episode_reward": reward,
            "reward_weights": dict(reward_weights or DEFAULT_REWARD_WEIGHTS),
            "components": {
                "par": par["par"],
                "tec": tec["tec"],
                "degradation_cost": degradation["degradation_cost"],
                "soc_satisfaction_ratio": satisfaction["soc_satisfaction_ratio"],
            },
        },
    }


def peak_to_average_ratio(samples: Sequence[Mapping[str, Any]]) -> dict[str, float | int | None]:
    powers = [_number_at(row, ("grid_power_kw", "P_grid", "actual_kw", "total_load_kw", "load_kw")) for row in samples]
    powers = [value for value in powers if value is not None]
    if not powers:
        return {"par": None, "peak_kw": None, "average_kw": None, "sample_count": 0}
    average_kw = mean(powers)
    peak_kw = max(powers)
    par = peak_kw / average_kw if average_kw > 0 else None
    return {
        "par": _round(par),
        "peak_kw": _round(peak_kw),
        "average_kw": _round(average_kw),
        "sample_count": len(powers),
    }


def total_energy_cost(
    samples: Sequence[Mapping[str, Any]],
    *,
    tick_minutes: float = DEFAULT_TICK_MINUTES,
    default_tariff: float = DEFAULT_TARIFF,
) -> dict[str, float | int]:
    """Compute net TEC in dollars.

    Positive power is charging cost. Negative signed power or explicit V2G
    revenue lowers the net cost.
    """
    gross_cost = 0.0
    v2g_revenue = 0.0
    energy_kwh = 0.0
    sample_count = 0

    for row in samples:
        duration_h = _duration_hours(row, tick_minutes)
        tariff = _number_at(row, ("tariff", "price", "price_per_kwh", "lambda_t"), default_tariff)
        power_kw = _number_at(row, ("power_kw", "P_k", "grid_power_kw", "actual_kw", "total_load_kw", "load_kw"))
        if power_kw is not None:
            sample_count += 1
            energy_kwh += power_kw * duration_h
            gross_cost += power_kw * tariff * duration_h
        revenue = _number_at(row, ("v2g_revenue", "revenue"), 0.0)
        v2g_revenue += revenue

    return {
        "tec": _round(gross_cost - v2g_revenue),
        "gross_energy_cost": _round(gross_cost),
        "v2g_revenue": _round(v2g_revenue),
        "net_energy_kwh": _round(energy_kwh),
        "sample_count": sample_count,
    }


def soc_satisfaction(
    ev_sessions: Sequence[Mapping[str, Any]],
    *,
    population: Mapping[str, Any] | None = None,
) -> dict[str, float | int | str | list[str] | None]:
    evaluable = 0
    satisfied = 0
    unsatisfied_ids: list[str] = []
    incomplete_ids: list[str] = []
    margins: list[float] = []

    for session in ev_sessions:
        final_soc = _number_at(session, ("final_soc", "departure_soc", "soc_final", "SoC_final", "battery_pct"))
        required_soc = _number_at(session, ("SoC_req_k", "required_soc", "soc_required", "target_soc", "request_soc"))
        if final_soc is None or required_soc is None:
            ev_id = _ev_id(session)
            if ev_id is not None:
                incomplete_ids.append(ev_id)
            continue
        evaluable += 1
        margin = final_soc - required_soc
        margins.append(margin)
        if margin >= 0:
            satisfied += 1
        else:
            unsatisfied_ids.append(_ev_id(session) or f"ev_{evaluable}")

    pop = dict(population or {})
    denominator = int(pop.get("total_evs") or 0)
    denominator_source = str(pop.get("denominator_source") or "")
    if denominator <= 0:
        denominator = len(ev_sessions) if ev_sessions else evaluable
        denominator_source = "sessions" if ev_sessions else "none"

    denominator = max(denominator, evaluable, len(set(incomplete_ids)))
    incomplete_count = max(0, denominator - evaluable)
    ratio = satisfied / denominator * 100.0 if denominator else None
    return {
        "soc_satisfaction_ratio": _round(ratio),
        "satisfied_evs": satisfied,
        "total_evs": denominator,
        "evaluable_evs": evaluable,
        "completed_evs": evaluable,
        "incomplete_evs": incomplete_count,
        "censored_evs": incomplete_count,
        "routed_evs": pop.get("routed_evs", 0),
        "admitted_evs": pop.get("admitted_evs", 0),
        "denominator_source": denominator_source,
        "unsatisfied_evs": unsatisfied_ids,
        "incomplete_ev_ids": sorted(set(incomplete_ids)),
        "mean_soc_margin_pct": _round(mean(margins)) if margins else None,
    }


def scheduling_lag(
    records: Sequence[Mapping[str, Any]],
    *,
    samples: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, float | int | bool | str | None]:
    per_ev: dict[str, dict[str, float]] = {}
    latency_fallback_ms: list[float] = []

    for record in records:
        payload = _payload(record)
        event_type = str(record.get("event_type") or payload.get("event_type") or payload.get("action") or "")
        ev_id = payload.get("ev_id") or record.get("ev_id") or payload.get("id")
        if ev_id is None:
            latency = _number_at(payload, ("latency_ms", "decision_latency_ms"))
            if latency is not None:
                latency_fallback_ms.append(latency)
            continue

        slot = per_ev.setdefault(str(ev_id), {})
        arrival = _number_at(payload, ("arrival_time_s", "arrival_s", "T_arrive_s", "arrive_time_s"))
        dispatch = _number_at(payload, ("dispatch_time_s", "decision_time_s", "T_dispatch_s", "scheduled_time_s"))
        if arrival is not None:
            slot["arrival"] = arrival
        if dispatch is not None:
            slot["dispatch"] = dispatch
        elif event_type in {"route", "dispatch", "schedule"}:
            timestamp_s = _timestamp_seconds(record.get("timestamp"))
            if timestamp_s is not None:
                slot["dispatch"] = timestamp_s

        latency = _number_at(payload, ("latency_ms", "decision_latency_ms"))
        if latency is not None:
            latency_fallback_ms.append(latency)

    lag_values = []
    lead_values = []
    for values in per_ev.values():
        if "arrival" not in values or "dispatch" not in values:
            continue
        signed = values["dispatch"] - values["arrival"]
        lag_values.append(max(0.0, signed))
        lead_values.append(max(0.0, -signed))

    lag_source = "arrival_dispatch"
    if not lag_values and samples:
        for row in samples:
            latency = _number_at(row, ("scheduling_lag_s", "lag_s"))
            if latency is not None:
                lag_values.append(max(0.0, latency))
                lag_source = "sample_lag"
            latency_ms = _number_at(row, ("latency_ms", "decision_latency_ms"))
            if latency_ms is not None:
                latency_fallback_ms.append(latency_ms)

    if lag_values:
        return {
            "mean_lag_seconds": _round(mean(lag_values)),
            "max_lag_seconds": _round(max(lag_values)),
            "mean_lead_seconds": _round(mean(lead_values)) if lead_values else 0.0,
            "ev_count": len(lag_values),
            "lag_source": lag_source,
            "is_latency_fallback": False,
            "latency_fallback_ms_avg": _round(mean(latency_fallback_ms)) if latency_fallback_ms else None,
        }

    return {
        "mean_lag_seconds": None,
        "max_lag_seconds": None,
        "mean_lead_seconds": None,
        "ev_count": 0,
        "lag_source": "latency_fallback" if latency_fallback_ms else "none",
        "is_latency_fallback": bool(latency_fallback_ms),
        "latency_fallback_ms_avg": _round(mean(latency_fallback_ms)) if latency_fallback_ms else None,
    }


def battery_degradation_cost(
    ev_sessions: Sequence[Mapping[str, Any]],
    *,
    tick_minutes: float = DEFAULT_TICK_MINUTES,
    degradation_rate: float = DEFAULT_DEGRADATION_RATE,
    battery_kwh: float = DEFAULT_BATTERY_KWH,
) -> dict[str, float | int]:
    total_cost = 0.0
    total_soc_throughput_pct = 0.0
    session_count = 0

    for session in ev_sessions:
        trajectory = _soc_trajectory(session)
        if len(trajectory) < 2:
            continue
        session_count += 1
        capacity = _number_at(session, ("battery_kwh", "capacity_kwh", "C_k"), battery_kwh)
        soh = _number_at(session, ("SoH_k", "soh"), 1.0)
        usable_kwh = max(0.1, capacity * soh)
        previous_tick, previous_soc = trajectory[0]
        for tick, soc in trajectory[1:]:
            delta_soc = abs(soc - previous_soc)
            if delta_soc <= 0:
                previous_tick, previous_soc = tick, soc
                continue
            dt_h = _trajectory_dt_hours(previous_tick, tick, tick_minutes)
            c_rate = _number_at(session, ("c_rate", "C_rate"))
            if c_rate is None:
                energy_kwh = usable_kwh * (delta_soc / 100.0)
                c_rate = energy_kwh / max(usable_kwh * dt_h, 1e-9)
            total_soc_throughput_pct += delta_soc
            total_cost += degradation_rate * c_rate * delta_soc
            previous_tick, previous_soc = tick, soc

    return {
        "degradation_cost": _round(total_cost),
        "soc_throughput_pct": _round(total_soc_throughput_pct),
        "session_count": session_count,
    }


def sensing_gain(
    isac_episodes: Sequence[Mapping[str, Any] | Sequence[Mapping[str, Any]]],
    no_isac_episodes: Sequence[Mapping[str, Any] | Sequence[Mapping[str, Any]]],
    *,
    reward_weights: Mapping[str, float] | None = None,
) -> dict[str, float | int | None]:
    isac_rewards = [_episode_reward_from_any(ep, reward_weights=reward_weights) for ep in isac_episodes]
    no_isac_rewards = [_episode_reward_from_any(ep, reward_weights=reward_weights) for ep in no_isac_episodes]
    isac_rewards = [value for value in isac_rewards if value is not None]
    no_isac_rewards = [value for value in no_isac_rewards if value is not None]

    if not isac_rewards or not no_isac_rewards:
        return {
            "delta_j": None,
            "relative_gain_pct": None,
            "isac_mean_reward": _round(mean(isac_rewards)) if isac_rewards else None,
            "no_isac_mean_reward": _round(mean(no_isac_rewards)) if no_isac_rewards else None,
            "isac_episode_count": len(isac_rewards),
            "no_isac_episode_count": len(no_isac_rewards),
        }

    isac_mean = mean(isac_rewards)
    no_isac_mean = mean(no_isac_rewards)
    delta = isac_mean - no_isac_mean
    relative = delta / abs(no_isac_mean) * 100.0 if abs(no_isac_mean) > 1e-12 else None
    return {
        "delta_j": _round(delta),
        "relative_gain_pct": _round(relative),
        "isac_mean_reward": _round(isac_mean),
        "no_isac_mean_reward": _round(no_isac_mean),
        "isac_episode_count": len(isac_rewards),
        "no_isac_episode_count": len(no_isac_rewards),
    }


def episode_reward(
    *,
    par: float | None,
    tec: float | None,
    degradation_cost: float | None,
    soc_satisfaction_ratio: float | None,
    weights: Mapping[str, float] | None = None,
) -> float | None:
    if par is None or tec is None or degradation_cost is None or soc_satisfaction_ratio is None:
        return None
    w = dict(DEFAULT_REWARD_WEIGHTS)
    if weights:
        w.update(weights)
    return _round(
        -w["par"] * par
        - w["tec"] * tec
        - w["degradation"] * degradation_cost
        + w["soc_satisfaction"] * (soc_satisfaction_ratio / 100.0)
    )


def _load_episode(source: Mapping[str, Any] | Sequence[Mapping[str, Any]] | str | Path) -> Any:
    if isinstance(source, (str, Path)):
        path = Path(source)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".jsonl":
            return [json.loads(line) for line in text.splitlines() if line.strip()]
        return json.loads(text)
    return source


def _samples(data: Any) -> list[Mapping[str, Any]]:
    if isinstance(data, Mapping):
        rows = data.get("full_samples") or data.get("samples") or data.get("timesteps") or data.get("ticks") or []
        return [row for row in rows if isinstance(row, Mapping)]
    return []


def _records(data: Any) -> list[Mapping[str, Any]]:
    if isinstance(data, Mapping):
        rows = data.get("records") or data.get("events") or data.get("chain") or []
        return [row for row in rows if isinstance(row, Mapping)]
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes)):
        return [row for row in data if isinstance(row, Mapping)]
    return []


def _sessions(data: Any, records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    by_ev: dict[str, dict[str, Any]] = {}
    anonymous: list[Mapping[str, Any]] = []

    def add(row: Mapping[str, Any]) -> None:
        ev_id = _ev_id(row)
        if ev_id is None:
            anonymous.append(row)
            return
        existing = by_ev.setdefault(ev_id, {"ev_id": ev_id})
        existing.update(row)

    if isinstance(data, Mapping):
        rows = data.get("ev_sessions") or data.get("sessions") or data.get("completed_evs") or []
        for row in rows:
            if isinstance(row, Mapping):
                add(row)
    for record in records:
        payload = _payload(record)
        event_type = str(record.get("event_type") or payload.get("event_type") or payload.get("action") or "")
        if event_type in {"route", "route_applied", "ev_arrived", "ev_admitted", "station_admit", "station_admitted"}:
            ev_row = _ev_row(payload)
            if ev_row:
                add(ev_row)
        elif event_type == "ev_completed" and payload:
            add(payload)
    return [*by_ev.values(), *anonymous]


def _ev_population(
    data: Any,
    records: Sequence[Mapping[str, Any]],
    sessions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    routed_ids: set[str] = set()
    admitted_ids: set[str] = set()

    for record in records:
        payload = _payload(record)
        event_type = str(record.get("event_type") or payload.get("event_type") or payload.get("action") or "")
        ev_id = _ev_id(payload)
        if ev_id is None:
            continue
        if event_type in {"route", "route_applied"}:
            routed_ids.add(ev_id)
        if event_type in {"ev_arrived", "ev_admitted", "station_admit", "station_admitted", "receive_ev"}:
            admitted_ids.add(ev_id)

    explicit_total = None
    explicit_routed = None
    explicit_admitted = None
    if isinstance(data, Mapping):
        explicit_total = _int_at(data, ("total_evs", "K_total", "ev_count"))
        explicit_routed = _int_at(data, ("routed_evs", "evs_routed", "routes_received"))
        explicit_admitted = _int_at(data, ("admitted_evs", "evs_admitted"))

    session_ids = {_ev_id(session) for session in sessions}
    session_ids.discard(None)
    routed_count = max(len(routed_ids), explicit_routed or 0)
    admitted_count = max(len(admitted_ids), explicit_admitted or 0)

    if explicit_total is not None:
        total_evs = explicit_total
        source = "explicit_total"
    elif routed_count:
        total_evs = routed_count
        source = "routed"
    elif admitted_count:
        total_evs = admitted_count
        source = "admitted"
    else:
        total_evs = len(session_ids) if session_ids else len(sessions)
        source = "sessions" if total_evs else "none"

    return {
        "total_evs": total_evs,
        "routed_evs": routed_count,
        "admitted_evs": admitted_count,
        "denominator_source": source,
    }


def _payload(record: Mapping[str, Any]) -> Mapping[str, Any]:
    payload = record.get("payload")
    return payload if isinstance(payload, Mapping) else record


def _ev_row(row: Mapping[str, Any]) -> Mapping[str, Any]:
    feature = row.get("ev_feature")
    if isinstance(feature, Mapping):
        return {**feature, **row}
    return row


def _ev_id(row: Mapping[str, Any]) -> str | None:
    ev_id = row.get("ev_id") or row.get("id")
    feature = row.get("ev_feature")
    if ev_id is None and isinstance(feature, Mapping):
        ev_id = feature.get("ev_id") or feature.get("id")
    return str(ev_id) if ev_id is not None else None


def _number_at(row: Mapping[str, Any], keys: Iterable[str], default: float | None = None) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _int_at(row: Mapping[str, Any], keys: Iterable[str]) -> int | None:
    value = _number_at(row, keys)
    return int(value) if value is not None else None


def _duration_hours(row: Mapping[str, Any], tick_minutes: float) -> float:
    seconds = _number_at(row, ("duration_s", "duration_seconds", "dt_s"))
    if seconds is not None:
        return seconds / 3600.0
    minutes = _number_at(row, ("duration_min", "dt_min", "tick_minutes"))
    if minutes is not None:
        return minutes / 60.0
    return tick_minutes / 60.0


def _infer_tick_minutes(samples: Sequence[Mapping[str, Any]]) -> float | None:
    minutes = [_number_at(row, ("minute", "t_min", "tick")) for row in samples]
    minutes = [value for value in minutes if value is not None]
    if len(minutes) < 2:
        return None
    deltas = [b - a for a, b in zip(minutes, minutes[1:]) if b > a]
    return min(deltas) if deltas else None


def _soc_trajectory(session: Mapping[str, Any]) -> list[tuple[float, float]]:
    raw = session.get("soc_trajectory") or session.get("SoC_trajectory") or session.get("trajectory") or []
    points: list[tuple[float, float]] = []
    for index, point in enumerate(raw):
        if isinstance(point, Mapping):
            tick = _number_at(point, ("tick", "minute", "time_min", "t"), float(index))
            soc = _number_at(point, ("soc", "soc_pct", "battery_pct", "SoC_k", "final_soc"))
        elif isinstance(point, Sequence) and not isinstance(point, (str, bytes)) and len(point) >= 2:
            tick = _coerce_float(point[0])
            soc = _coerce_float(point[1])
        else:
            tick = float(index)
            soc = _coerce_float(point)
        if tick is not None and soc is not None:
            points.append((tick, soc))
    return points


def _trajectory_dt_hours(previous_tick: float, tick: float, default_tick_minutes: float) -> float:
    delta = tick - previous_tick
    if delta > 0:
        return delta * default_tick_minutes / 60.0
    return default_tick_minutes / 60.0


def _timestamp_seconds(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _episode_reward_from_any(
    episode: Mapping[str, Any] | Sequence[Mapping[str, Any]],
    *,
    reward_weights: Mapping[str, float] | None,
) -> float | None:
    if isinstance(episode, Mapping):
        direct = _number_at(episode, ("episode_reward", "reward", "cumulative_reward", "J"))
        if direct is not None:
            return direct
        if "sensing_gain_inputs" in episode:
            inputs = episode["sensing_gain_inputs"]
            if isinstance(inputs, Mapping):
                direct = _number_at(inputs, ("episode_reward", "reward", "J"))
                if direct is not None:
                    return direct
    evaluated = evaluate_episode(episode, reward_weights=reward_weights)
    return evaluated["sensing_gain_inputs"]["episode_reward"]


def _coerce_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)
