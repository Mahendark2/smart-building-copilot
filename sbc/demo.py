"""Keeps the simulated building's faults in step with the demo_faults table."""
from . import db


def sync(building):
    try:
        building.set_faults({z: f for z, (f, _) in db.demo_faults().items()})
    except Exception as e:  # the database may not be up yet; try again next time
        print(f"demo fault sync skipped: {e}", flush=True)


def seed(faults):
    try:
        db.setup()
        db.seed_demo_faults(faults)
    except Exception as e:
        print(f"could not seed demo faults: {e}", flush=True)
