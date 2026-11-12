"""Simulated BACnet/IP controller with 72 HVAC points.

Run:  python -m sbc.simulator --name SBC-Controller --instance 1001 --address 127.0.0.1/8:47808
Faults: set FAULTS=3:stuck_damper,5:sensor_drift (see model.FAULT_TYPES)
"""
import asyncio
import os

from bacpypes3.app import Application
from bacpypes3.argparse import SimpleArgumentParser
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.local.binary import BinaryValueObject

from .model import Building, parse_faults
from .points import POINTS

UNITS = {"degC": "degreesCelsius", "percent": "percent", "ppm": "partsPerMillion"}


def make_objects():
    objs = {}
    for p in POINTS:
        if p["object_type"] == "analog-value":
            o = AnalogValueObject(
                objectIdentifier=("analog-value", p["instance"]),
                objectName=p["name"],
                presentValue=0.0,
                statusFlags=[0, 0, 0, 0],
                covIncrement=0.1,
                units=UNITS[p["units"]],
            )
        else:
            o = BinaryValueObject(
                objectIdentifier=("binary-value", p["instance"]),
                objectName=p["name"],
                presentValue="inactive",
                statusFlags=[0, 0, 0, 0],
            )
        objs[p["name"]] = o
    return objs


def push(objs, values):
    for name, v in values.items():
        o = objs[name]
        if name.endswith(("fan_status", "occupied")):
            o.presentValue = "active" if v else "inactive"
        else:
            o.presentValue = float(v)


async def main():
    parser = SimpleArgumentParser()
    args = parser.parse_args()
    tick = float(os.getenv("SIM_TICK", "2"))
    building = Building(faults=parse_faults(os.getenv("FAULTS", "3:stuck_damper,5:sensor_drift")))

    app = Application.from_args(args)
    objs = make_objects()
    for o in objs.values():
        app.add_object(o)
    print(f"simulator up with {len(objs)} points on {args.address or 'host'}", flush=True)

    try:
        while True:
            building.step()
            push(objs, building.values())
            await asyncio.sleep(tick)
    finally:
        app.close()


if __name__ == "__main__":
    asyncio.run(main())
