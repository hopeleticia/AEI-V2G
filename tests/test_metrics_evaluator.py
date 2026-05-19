from metrics.evaluator import (
    battery_degradation_cost,
    evaluate_episode,
    peak_to_average_ratio,
    scheduling_lag,
    sensing_gain,
    soc_satisfaction,
    total_energy_cost,
)


def test_par_and_tec_use_episode_samples_without_mutation():
    samples = [
        {"minute": 0, "actual_kw": 10.0, "tariff": 0.20},
        {"minute": 1, "actual_kw": 20.0, "tariff": 0.30, "v2g_revenue": 1.0},
        {"minute": 2, "actual_kw": -5.0, "tariff": 0.40},
    ]
    original = [dict(row) for row in samples]

    assert peak_to_average_ratio(samples)["par"] == 2.4
    tec = total_energy_cost(samples, tick_minutes=60.0)

    assert tec["gross_energy_cost"] == 6.0
    assert tec["tec"] == 5.0
    assert samples == original


def test_soc_satisfaction_and_degradation_from_sessions():
    sessions = [
        {
            "ev_id": "ev-a",
            "final_soc": 82.0,
            "SoC_req_k": 80.0,
            "soc_trajectory": [(0, 60.0), (1, 70.0), (2, 82.0)],
            "battery_kwh": 72.0,
        },
        {
            "ev_id": "ev-b",
            "final_soc": 74.0,
            "SoC_req_k": 80.0,
            "soc_trajectory": [(0, 84.0), (1, 78.0), (2, 74.0)],
            "battery_kwh": 72.0,
        },
    ]

    satisfaction = soc_satisfaction(sessions)
    degradation = battery_degradation_cost(sessions, tick_minutes=60.0, degradation_rate=0.01)

    assert satisfaction["soc_satisfaction_ratio"] == 50.0
    assert satisfaction["unsatisfied_evs"] == ["ev-b"]
    assert degradation["soc_throughput_pct"] == 32.0
    assert degradation["degradation_cost"] == 0.0296


def test_soc_satisfaction_uses_routed_denominator_for_incomplete_evs():
    episode = {
        "events": [
            {"event_type": "route", "payload": {"ev_id": "ev-a", "SoC_req_k": 80.0}},
            {"event_type": "route", "payload": {"ev_id": "ev-b", "SoC_req_k": 80.0}},
            {
                "event_type": "ev_completed",
                "payload": {"ev_id": "ev-a", "final_soc": 82.0, "SoC_req_k": 80.0},
            },
        ],
    }

    satisfaction = evaluate_episode(episode)["soc_satisfaction"]

    assert satisfaction["soc_satisfaction_ratio"] == 50.0
    assert satisfaction["satisfied_evs"] == 1
    assert satisfaction["total_evs"] == 2
    assert satisfaction["evaluable_evs"] == 1
    assert satisfaction["incomplete_evs"] == 1
    assert satisfaction["censored_evs"] == 1
    assert satisfaction["routed_evs"] == 2
    assert satisfaction["denominator_source"] == "routed"
    assert satisfaction["incomplete_ev_ids"] == ["ev-b"]


def test_scheduling_lag_prefers_per_ev_times_and_tracks_lead():
    records = [
        {"event_type": "route", "payload": {"ev_id": "early", "arrival_time_s": 100.0, "dispatch_time_s": 90.0}},
        {"event_type": "route", "payload": {"ev_id": "late", "arrival_time_s": 100.0, "dispatch_time_s": 140.0}},
    ]

    lag = scheduling_lag(records)

    assert lag["mean_lag_seconds"] == 20.0
    assert lag["max_lag_seconds"] == 40.0
    assert lag["mean_lead_seconds"] == 5.0
    assert lag["ev_count"] == 2
    assert lag["lag_source"] == "arrival_dispatch"
    assert lag["is_latency_fallback"] is False


def test_scheduling_lag_keeps_compute_latency_out_of_physical_lag():
    records = [
        {"event_type": "route", "payload": {"ev_id": "ev-a", "latency_ms": 7.5}},
        {"event_type": "v2g_dispatch", "payload": {"latency_ms": 2.5}},
    ]

    lag = scheduling_lag(records)

    assert lag["mean_lag_seconds"] is None
    assert lag["max_lag_seconds"] is None
    assert lag["ev_count"] == 0
    assert lag["lag_source"] == "latency_fallback"
    assert lag["is_latency_fallback"] is True
    assert lag["latency_fallback_ms_avg"] == 5.0


def test_evaluate_episode_and_sensing_gain_inputs():
    episode = {
        "samples": [
            {"minute": 0, "actual_kw": 100.0, "tariff": 0.10},
            {"minute": 1, "actual_kw": 50.0, "tariff": 0.20},
        ],
        "events": [
            {
                "event_type": "ev_completed",
                "payload": {
                    "ev_id": "ev-a",
                    "final_soc": 90.0,
                    "SoC_req_k": 80.0,
                    "soc_trajectory": [(0, 70.0), (1, 90.0)],
                },
            }
        ],
    }

    metrics = evaluate_episode(episode, tick_minutes=60.0)

    assert metrics["par"]["par"] == 1.333333
    assert metrics["tec"]["tec"] == 20.0
    assert metrics["soc_satisfaction"]["soc_satisfaction_ratio"] == 100.0
    assert metrics["sensing_gain_inputs"]["episode_reward"] is not None

    gain = sensing_gain(
        [metrics["sensing_gain_inputs"], {"episode_reward": 1.5}],
        [{"episode_reward": 1.0}],
    )
    assert gain["delta_j"] is not None
    assert gain["isac_episode_count"] == 2
