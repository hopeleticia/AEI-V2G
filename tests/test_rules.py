from lava.rules import RuleReasoner
from sim.corridor import Corridor


def test_low_battery_rule_uses_nearest_station():
    corridor = Corridor.from_yaml("config/corridor_config.yaml")
    rules = RuleReasoner({"low_battery_threshold": 25, "critical_grid_stress": 0.8, "v2g_min_battery": 55, "max_wait_minutes": 18})
    feature = {"battery_pct": 12, "nearest_station_id": "station_a", "km": 2}
    assert rules.recommend_station(feature, corridor.stations, {"stress": 0.2}).station_id == "station_a"
