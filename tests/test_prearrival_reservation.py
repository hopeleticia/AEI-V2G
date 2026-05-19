from integration.coordinator import run
from sim.entities import EV, Station
from sim.station_model import receive_ev


def test_station_reservation_holds_slot_until_ev_arrives():
    station = Station("s1", km=10.0, max_kw=150.0, slots=1, base_price=0.3)
    reservation = station.reserve_slot("ev_1", eta_min=5.0, tick=2)

    assert station.available_slots == 0
    assert reservation["status"] == "reserved"

    ev = EV("ev_1", km=10.0, speed_kmh=0.0, battery_pct=40.0, destination_km=20.0, charge_request=True, required_kwh=10.0)
    receive_ev(station, ev)

    assert station.active_evs == [ev]
    assert station.reservations == {}


def test_standalone_run_logs_prearrival_reservations(tmp_path):
    chain_path = tmp_path / "chain.jsonl"
    run("config/corridor_config.yaml", 1800, str(tmp_path / "metrics.json"), str(chain_path))

    text = chain_path.read_text(encoding="utf-8")
    assert '"event_type": "slot_reserved"' in text
