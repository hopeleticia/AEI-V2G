from sim.corridor import Corridor


def test_corridor_spawns_and_senses_evs():
    corridor = Corridor.from_yaml("config/corridor_config.yaml")
    evs = corridor.generator.spawn(10, corridor.length_km)
    assert evs
    sensed = corridor.sense(evs)
    assert isinstance(sensed, list)
