"""Start the whole project with one command, no Docker or PostgreSQL needed.

    python run.py                 # real BACnet/IP between simulator and gateway
    python run.py --no-bacnet     # if BACnet can't bind on your machine
    python run.py --port 9000

Then open http://localhost:8080
Uses SQLite in ./data unless DATABASE_URL is set. Reads LLM settings from .env.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent


def load_env():
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            if v.strip() and k.strip() not in os.environ:
                os.environ[k.strip()] = v.strip()


def start(name, args, env):
    print(f"starting {name}", flush=True)
    return subprocess.Popen([sys.executable, "-m", *args], cwd=ROOT, env=env)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8080)
    ap.add_argument("--no-bacnet", action="store_true")
    opt = ap.parse_args()

    load_env()
    (ROOT / "data").mkdir(exist_ok=True)
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'sbc.db'}")
    os.environ.setdefault("SIM_TICK", "1")
    os.environ.setdefault("POLL_SECONDS", "2")
    os.environ["API_URL"] = f"http://127.0.0.1:{opt.port}/api"
    env = dict(os.environ)

    from sbc import db
    db.setup()

    procs = []
    if opt.no_bacnet:
        procs.append(start("feeder (no BACnet)", ["sbc.feeder"], env))
    else:
        procs.append(start("BACnet simulator", ["sbc.simulator", "--name", "SBC-Controller",
                                                "--instance", "1001", "--address", "127.0.0.1/8:47808"], env))
        time.sleep(1.5)
        env["CONTROLLER"] = "127.0.0.1:47808"
        procs.append(start("BACnet gateway", ["sbc.gateway", "--name", "SBC-Gateway",
                                              "--instance", "1002", "--address", "127.0.0.1/8:47809"], env))

    import uvicorn
    from a2wsgi import WSGIMiddleware
    from fastapi import FastAPI
    from fastapi.staticfiles import StaticFiles

    from sbc import api, assistant

    app = FastAPI()
    app.mount("/api", api.app)
    app.mount("/assistant", WSGIMiddleware(assistant.app))
    dist = ROOT / "web" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True))
    else:
        print("web/dist is missing: run 'npm install && npm run build' in web/", flush=True)

    llm = "set" if (os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")) else "NOT set (chat will ask for a key)"
    print(f"\n  Dashboard:  http://localhost:{opt.port}\n  API docs:   http://localhost:{opt.port}/api/docs"
          f"\n  LLM key:    {llm}\n  Stop:       Ctrl+C\n", flush=True)
    try:
        uvicorn.run(app, host="127.0.0.1", port=opt.port, log_level="warning")
    finally:
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
