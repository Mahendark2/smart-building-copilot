import os
from datetime import timedelta

import pytest

os.environ["SKIP_DB_SETUP"] = "1"

from sbc import db  # noqa: E402
from sbc.model import Building  # noqa: E402


@pytest.fixture(scope="session")
def filled_db(tmp_path_factory):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        url = f"sqlite:///{tmp_path_factory.mktemp('db') / 'test.db'}"
    db.reset(url)
    db.Base.metadata.drop_all(db.engine())
    db.setup()

    b = Building(faults={3: "stuck_damper", 5: "sensor_drift", 2: "fan_off"})
    start = db.now() - timedelta(minutes=20)
    for i in range(60):
        b.step()
        db.save_readings(b.values(), ts=start + timedelta(seconds=20 * i))
    return url
