from integration.v2g_dispatcher import apply_v2g
from sim.entities import EV, Station


def test_v2g_dispatch_invites_and_supplies_energy():
    station = Station("s1", 1, 300, 4, 0.3)
    station.active_evs.append(EV("ev1", 1, 0, 80, 10, False, 0))
    result = apply_v2g({"s1": station}, 20, 60, 0.5)
    assert result["invited"] == 1
    assert result["accepted"] == 1
    assert result["supplied_kwh"] > 0
