from __future__ import annotations

from sim.entities import EV, Station


def nearest_station(ev: EV, stations: dict[str, Station]) -> str:
    reachable = [station for station in stations.values() if station.km >= ev.km]
    return min(reachable or list(stations.values()), key=lambda station: abs(station.km - ev.km)).id
