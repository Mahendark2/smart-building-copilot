"""BACnet/IP gateway: reads all 72 points from the controller and saves them.

Run:  python -m sbc.gateway --address 127.0.0.1/8:47809
Env:  CONTROLLER=127.0.0.1:47808  POLL_SECONDS=5  DATABASE_URL=...
"""
import asyncio
import os
import socket

from bacpypes3.apdu import ErrorRejectAbortNack
from bacpypes3.app import Application
from bacpypes3.argparse import SimpleArgumentParser

from . import db
from .points import POINTS


def controller_address():
    raw = os.getenv("CONTROLLER", "127.0.0.1:47808")
    host, _, port = raw.partition(":")
    ip = socket.gethostbyname(host)  # lets us use a Docker service name
    return f"{ip}:{port or 47808}"


def to_number(p, v):
    if p["object_type"] == "binary-value":
        return 1.0 if str(v).lower() in ("active", "1") else 0.0
    return float(v)


async def read_all(app, addr):
    async def one(p):
        try:
            v = await app.read_property(addr, f"{p['object_type']},{p['instance']}", "present-value")
            return p["name"], to_number(p, v)
        except (ErrorRejectAbortNack, Exception) as e:
            print(f"read failed {p['name']}: {e}", flush=True)
            return p["name"], None

    results = await asyncio.gather(*(one(p) for p in POINTS))
    return {n: v for n, v in results if v is not None}


async def main():
    args = SimpleArgumentParser().parse_args()
    every = float(os.getenv("POLL_SECONDS", "5"))
    db.setup()
    app = Application.from_args(args)
    addr = controller_address()
    print(f"gateway polling {addr} every {every}s", flush=True)

    try:
        while True:
            vals = await read_all(app, addr)
            if vals:
                db.save_readings(vals)
            print(f"saved {len(vals)}/{len(POINTS)} points", flush=True)
            await asyncio.sleep(every)
    finally:
        app.close()


if __name__ == "__main__":
    asyncio.run(main())
