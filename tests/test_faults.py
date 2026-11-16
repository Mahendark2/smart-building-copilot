from sbc.faults import detect
from sbc.model import Building


def frames_from(b, steps, frames=None, shift=0.0):
    frames = frames or {z: {} for z in range(1, 7)}
    for _ in range(steps):
        b.step()
        for k, v in b.values().items():
            z, kind = int(k[4]), k.split(".")[1]
            if kind == "supply_air_temp":
                v += shift
            frames[z].setdefault(kind, []).append(v)
    return frames


def test_restart_jump_is_not_drift():
    # every zone jumps together, like after a restart: no zone should be blamed
    fr = frames_from(Building(), 20)
    fr = frames_from(Building(start_hour=14), 20, fr, shift=1.5)
    assert not [f for f in detect(fr) if f["type"] == "supply_sensor_drift"]


def test_real_drift_is_found():
    fr = frames_from(Building(faults={5: "sensor_drift"}), 60)
    drift = [f for f in detect(fr) if f["type"] == "supply_sensor_drift"]
    assert [f["zone"] for f in drift] == [5]


def test_drift_that_stopped_is_still_found():
    # long enough for the drift to hit its cap and stop moving
    fr = frames_from(Building(faults={5: "sensor_drift"}), 200)
    drift = [f for f in detect(fr) if f["type"] == "supply_sensor_drift"]
    assert [f["zone"] for f in drift] == [5]
    assert "warmer than the rest" in drift[0]["detail"]


def test_drift_is_capped():
    b = Building(faults={5: "sensor_drift"})
    for _ in range(500):
        b.step()
    v = b.values()
    assert v["zone5.supply_air_temp"] - v["zone1.supply_air_temp"] < 6
