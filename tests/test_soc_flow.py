from integration.v2g_dispatcher import apply_v2g
from sim.entities import EV, Station
from sim.rsu_model import RSU
from sim.station_model import receive_ev, update_station


def test_rsu_feature_carries_per_ev_battery_state():
    station = Station("s1", km=10.0, max_kw=150.0, slots=2, base_price=0.3)
    ev = EV(
        id="ev_soc",
        km=4.5,
        speed_kmh=90.0,
        battery_pct=41.0,
        destination_km=20.0,
        charge_request=True,
        required_kwh=20.0,
        SoH_k=0.87,
        SoC_req_k=88.0,
        T_dep_k=75.0,
    )

    feature = RSU("r1", km=4.0, range_km=7.5).sense([ev], {"s1": station})[0]

    assert feature["SoC_k"] == ev.battery_pct
    assert feature["SoH_k"] == 0.87
    assert feature["SoC_req_k"] == 88.0
    assert feature["T_dep_k"] == 75.0
    assert feature["estimated_soc"] is not None
    assert abs(feature["estimated_soc"] - ev.battery_pct) < 15.0
    assert feature["estimated_soc_confidence"] > 0.0
    assert {"rssi_dbm", "doppler_hz", "range_km", "decel_mps2"} <= set(feature["isac_proxy_features"])


def test_station_charge_updates_soc_trajectory_and_completion_fields():
    station = Station("s1", km=1.0, max_kw=150.0, slots=1, base_price=0.3)
    ev = EV(
        id="ev_charge",
        km=1.0,
        speed_kmh=0.0,
        battery_pct=50.0,
        destination_km=2.0,
        charge_request=True,
        required_kwh=5.0,
        assigned_station="s1",
        SoH_k=0.9,
        SoC_req_k=70.0,
        T_dep_k=45.0,
    )
    receive_ev(station, ev)

    completed = update_station(station, tick_minutes=60.0, tick=7)

    assert completed == [ev]
    assert ev.SoH_k == 0.9
    assert ev.SoC_req_k == 70.0
    assert ev.T_dep_k == 45.0
    assert ev.soc_trajectory[0] == (0, 50.0)
    assert ev.soc_trajectory[-1][0] == 7
    assert ev.soc_trajectory[-1][1] > 50.0


def test_v2g_updates_soc_trajectory_and_reports_actual_safe_energy():
    station = Station("s1", km=1.0, max_kw=300.0, slots=2, base_price=0.3)
    ev = EV(
        id="ev_v2g",
        km=1.0,
        speed_kmh=0.0,
        battery_pct=62.1,
        destination_km=2.0,
        charge_request=True,
        required_kwh=0.0,
        assigned_station="s1",
        SoH_k=1.0,
    )
    station.active_evs.append(ev)

    result = apply_v2g({"s1": station}, dispatch_kw=12.0, tick_minutes=300.0, buy_price=0.5, tick=9)

    assert result["invited"] == 1
    assert result["accepted"] == 1
    assert result["supplied_kwh"] < 60.0
    assert result["credits_awarded"] == int(result["supplied_kwh"] / 0.5)
    assert result["settlements"][0]["ev_id"] == "ev_v2g"
    assert ev.battery_pct == 20.0
    assert ev.soc_trajectory[-1] == (9, 20.0)
    assert station.v2g_supplied_kwh == result["supplied_kwh"]


def test_v2g_discharge_extends_completion_obligation_to_requested_soc():
    station = Station("s1", km=1.0, max_kw=300.0, slots=1, base_price=0.3)
    ev = EV(
        id="ev_v2g_completion",
        km=1.0,
        speed_kmh=0.0,
        battery_pct=70.0,
        destination_km=2.0,
        charge_request=True,
        required_kwh=5.76,
        assigned_station="s1",
        SoH_k=0.8,
        SoC_req_k=80.0,
    )
    station.active_evs.append(ev)

    result = apply_v2g({"s1": station}, dispatch_kw=12.0, tick_minutes=60.0, buy_price=0.5, tick=3)

    assert result["supplied_kwh"] == 12.0
    assert result["settlements"][0]["credits_awarded"] == 24
    assert round(ev.battery_pct, 2) == 49.17
    assert round(ev.required_kwh, 2) == 17.76

    completed = update_station(station, tick_minutes=60.0, tick=4)

    assert completed == [ev]
    assert ev.battery_pct >= ev.SoC_req_k
    assert ev.required_kwh <= 0.1
