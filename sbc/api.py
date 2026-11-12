"""FastAPI backend. Stateless: every request reads from PostgreSQL, so any copy
behind Nginx can answer any request.

Run:  uvicorn sbc.api:app --port 8000
"""
import os
import socket
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from . import db, faults
from .points import BY_NAME, ZONES


@asynccontextmanager
async def lifespan(app):
    if os.getenv("SKIP_DB_SETUP") != "1":
        db.setup()
    yield


# ROOT_PATH=/api behind Nginx so the /docs page finds its schema
app = FastAPI(title="Smart Building Copilot API", version="1.0", lifespan=lifespan,
              root_path=os.getenv("ROOT_PATH", ""))
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
HOST = socket.gethostname()


@app.middleware("http")
async def served_by(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Served-By"] = HOST  # shows which copy answered
    return resp


@app.get("/health")
def health():
    try:
        n = len(db.latest())
        return {"status": "ok", "host": HOST, "points_with_data": n}
    except Exception as e:
        raise HTTPException(503, f"database not reachable: {e}")


@app.get("/points")
def points(zone: int | None = None):
    data = db.latest()
    if zone is not None:
        data = [p for p in data if p["zone"] == zone]
    return data


@app.get("/points/{name}/history")
def history(name: str, minutes: int = 60):
    if name not in BY_NAME:
        raise HTTPException(404, f"no point called {name}")
    minutes = max(1, min(minutes, 24 * 60))
    return {"name": name, "units": BY_NAME[name]["units"],
            "readings": db.history(name, db.now() - timedelta(minutes=minutes))}


@app.get("/zones/{zone}")
def zone_summary(zone: int):
    if not 1 <= zone <= ZONES:
        raise HTTPException(404, f"zones are 1 to {ZONES}")
    vals = {p["kind"]: p["value"] for p in db.latest() if p["zone"] == zone}
    zone_faults = [f for f in detect(30) if f["zone"] == zone]
    return {"zone": zone, "values": vals, "faults": zone_faults}


def detect(minutes):
    since = db.now() - timedelta(minutes=minutes)
    frames = {z: db.zone_frame(z, since) for z in range(1, ZONES + 1)}
    return faults.detect(frames)


@app.get("/faults")
def get_faults(minutes: int = 30):
    minutes = max(1, min(minutes, 24 * 60))
    return {"window_minutes": minutes, "faults": detect(minutes)}
