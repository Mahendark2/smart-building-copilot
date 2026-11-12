from fastapi.testclient import TestClient

from sbc.api import app

client = TestClient(app)


def test_health(filled_db):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["points_with_data"] == 72
    assert "X-Served-By" in r.headers


def test_points_by_zone(filled_db):
    r = client.get("/points", params={"zone": 2})
    assert r.status_code == 200
    assert len(r.json()) == 12


def test_history(filled_db):
    r = client.get("/points/zone1.zone_temp/history", params={"minutes": 60})
    assert r.status_code == 200
    assert len(r.json()["readings"]) == 60


def test_unknown_point_is_404(filled_db):
    assert client.get("/points/zone9.nope/history").status_code == 404


def test_faults_found_in_the_right_zones(filled_db):
    found = client.get("/faults").json()["faults"]
    kinds = {(f["zone"], f["type"]) for f in found}
    assert (3, "stuck_damper") in kinds
    assert (2, "fan_off_while_occupied") in kinds
    assert (5, "supply_sensor_drift") in kinds
    assert not [f for f in found if f["zone"] in (1, 4, 6) and f["severity"] == "high"]


def test_zone_summary(filled_db):
    r = client.get("/zones/3").json()
    assert r["values"]["damper_pos"] == 0
    assert any(f["type"] == "stuck_damper" for f in r["faults"])
