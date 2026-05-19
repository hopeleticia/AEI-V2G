from __future__ import annotations

from sim.entities import EV, Station


def update_station(station: Station, tick_minutes: float, tick: int = 0) -> list[EV]:
    completed: list[EV] = []
    station.expire_reservations(tick)
    for ev in list(station.active_evs):
        ev.refresh_required_kwh_for_request()
        requested = min(ev.required_kwh, 55.0 * tick_minutes / 60.0)
        delivered = ev.add_charge_kwh(requested, tick)
        ev.required_kwh -= delivered
        station.energy_delivered_kwh += delivered
        if ev.required_kwh <= 0.1 and ev.has_met_requested_soc():
            station.active_evs.remove(ev)
            completed.append(ev)
    while station.available_slots and station.queue:
        station.active_evs.append(station.queue.pop(0))
    return completed


def receive_ev(station: Station, ev: EV) -> None:
    station.release_reservation(ev.id)
    if station.available_slots:
        station.active_evs.append(ev)
    else:
        station.queue.append(ev)
