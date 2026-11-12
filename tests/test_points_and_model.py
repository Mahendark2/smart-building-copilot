from sbc.model import Building, parse_faults
from sbc.points import POINTS


def test_72_unique_points():
    assert len(POINTS) == 72
    assert len({p["name"] for p in POINTS}) == 72
    assert len({(p["object_type"], p["instance"]) for p in POINTS}) == 72


def test_building_gives_a_value_for_every_point():
    vals = Building().values()
    assert set(vals) == {p["name"] for p in POINTS}


def test_stuck_damper_makes_zone_warm():
    b = Building(faults={3: "stuck_damper"})
    for _ in range(90):
        b.step()
    v = b.values()
    assert v["zone3.damper_pos"] == 0
    assert v["zone3.zone_temp"] > v["zone1.zone_temp"] + 3


def test_parse_faults():
    assert parse_faults("3:stuck_damper, 5:sensor_drift") == {3: "stuck_damper", 5: "sensor_drift"}
    assert parse_faults("") == {}
