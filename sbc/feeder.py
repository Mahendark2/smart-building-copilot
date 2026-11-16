"""Fallback for machines where BACnet/IP can't bind (some Windows setups).
Runs the same building model and saves values straight to the database,
skipping the BACnet hop. Use only if the gateway can't read the simulator.
"""
import os
import time

from . import db
from . import demo
from .model import Building, parse_faults


def main():
    tick = float(os.getenv("SIM_TICK", "1"))
    every = float(os.getenv("POLL_SECONDS", "2"))
    db.setup()
    faults = parse_faults(os.getenv("FAULTS", "3:stuck_damper,5:sensor_drift"))
    b = Building(faults=faults)
    demo.seed(faults)
    print("feeder running without BACnet (direct mode)", flush=True)
    while True:
        demo.sync(b)
        for _ in range(max(1, round(every / tick))):
            b.step()
        db.save_readings(b.values())
        time.sleep(every)


if __name__ == "__main__":
    main()
