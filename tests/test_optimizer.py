from lava.optimizer import GlobalOptimizer
from sim.corridor import Corridor


def test_optimizer_returns_reachable_station():
    corridor = Corridor.from_yaml("config/corridor_config.yaml")
    optimizer = GlobalOptimizer({"grid_stress": 0.3, "ev_wait_time": 0.3, "station_imbalance": 0.2, "energy_cost": 0.2})
    feature = {"eta_by_station_min": {"station_a": 5, "station_b": 20}, "km": 3, "battery_pct": 50}
    candidate = optimizer.recommend_station(feature, corridor.stations, {"stress": 0.5, "tariff": 0.3})
    assert candidate.station_id in corridor.stations
    assert candidate.confidence > 0
