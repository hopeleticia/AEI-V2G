from lava.constraints import ConstraintEnforcer
from sim.corridor import Corridor


def test_constraints_return_station_candidate():
    corridor = Corridor.from_yaml("config/corridor_config.yaml")
    constraints = ConstraintEnforcer(
        {
            "max_station_utilization": 0.98,
            "max_grid_frequency_deviation_hz": 0.25,
            "min_battery_after_v2g": 20,
        }
    )
    feature = {"eta_by_station_min": {"station_a": 10, "station_b": 30, "station_c": 50}}
    candidate = constraints.recommend_station(feature, corridor.stations, {"frequency_hz": 50})
    assert candidate.station_id in corridor.stations
