# Smart Building Copilot

An AI assistant for building operators. It reads 72 HVAC points from a
**simulated** BACnet/IP controller, stores them in PostgreSQL, finds faults with
rules plus a machine learning model, and lets staff ask questions in plain
English. An LLM agent answers by calling the building API as tools.

![dashboard](docs/dashboard.png)

## How it fits together

```
 Simulated controller        Gateway             PostgreSQL
 (BACpypes3, 72 points) --> (BACpypes3 client) --> points, readings
        BACnet/IP UDP 47808     polls every 5 s           |
                                                          v
 React dashboard  -->  Nginx  -->  FastAPI x3 (stateless, ML fault detection)
                         |
                         +-->  Flask assistant  --> LLM (OpenAI-compatible)
                                   |   tool calls
                                   +--> back to the API through Nginx
```

| Part | Folder | What it does |
| --- | --- | --- |
| Simulator | `sbc/simulator.py`, `sbc/model.py` | A BACnet/IP device with 6 zones x 12 points. A small physics model moves the values, and faults can be switched on. |
| Gateway | `sbc/gateway.py` | Reads every point's present-value over BACnet/IP and saves a row per point. |
| API | `sbc/api.py` | FastAPI. Latest values, history, zone summaries, faults. Keeps no state, so 3 copies run behind Nginx. |
| Fault detection | `sbc/faults.py` | Rules for known faults, plus an Isolation Forest that flags zones that look unlike the rest. |
| Assistant | `sbc/assistant.py` | Flask. Sends the question and 4 tools to the LLM, runs the tools it asks for, loops until it can answer (up to 6 steps). |
| Dashboard | `web/` | React and Vite. Live zone cards, a fault list and a chat panel. |
| Tests | `tests/` | 13 Pytest tests, including the tool loop with a fake LLM. Run on SQLite and PostgreSQL in CI. |

### The points

Each zone has: room temperature, cooling and heating setpoints, supply and return
air temperature, humidity, CO2, damper position, cooling valve position, fan
speed, fan status and occupancy. Zone `z` uses BACnet instances `z*100 + 1` to
`z*100 + 12` (analog-value for numbers, binary-value for on/off).

### The faults

| Fault | How it is found |
| --- | --- |
| Stuck damper | Damper under 5% while the valve is over 80% open and the room is 1.5 C over setpoint |
| Fan off while occupied | Occupied but the fan is off for the whole window |
| Supply sensor drift | Supply air rises over 0.5 C across 30 readings while the valve stays steady |
| High CO2 | Over 1000 ppm |
| Unusual behaviour | Isolation Forest marks most of a zone's last 5 readings as outliers |

Switch faults on with `FAULTS=3:stuck_damper,5:sensor_drift` (also `fan_off`, `high_co2`).

## Run it with Docker

```bash
cp .env.example .env        # add LLM_API_KEY to use the chat
docker compose up --build
```

Open http://localhost:8080. The dashboard fills in after about 10 seconds.
Check which API copy answered with `curl -i localhost:8080/api/health` and look at
`X-Served-By`; repeat it and the name changes.

The chat works with any OpenAI-compatible provider. Set `LLM_BASE_URL` for one
that is not OpenAI (Groq, Together, a local Ollama at
`http://host.docker.internal:11434/v1`, and so on).

## Run it without Docker

You need Python 3.12+, Node 20+ and PostgreSQL.

```bash
pip install -r requirements-dev.txt
createdb sbc        # or point DATABASE_URL at any PostgreSQL
export DATABASE_URL=postgresql+psycopg2://USER:PASS@localhost:5432/sbc

# 1. controller and gateway (two terminals). They use different ports on one machine.
python -m sbc.simulator --name SBC-Controller --instance 1001 --address 127.0.0.1/8:47808
CONTROLLER=127.0.0.1:47808 python -m sbc.gateway --instance 1002 --address 127.0.0.1/8:47809

# 2. API and assistant
uvicorn sbc.api:app --port 8000
LLM_API_KEY=... flask --app sbc.assistant run --port 5000

# 3. dashboard
cd web && npm install && npm run dev
```

## Tests

```bash
pytest -q                                   # SQLite, no setup
TEST_DATABASE_URL=postgresql+psycopg2://... pytest -q
```

GitHub Actions runs both, builds the dashboard, and builds every Docker image on
each push (`.github/workflows/ci.yml`).

## API

| Method | Path | Returns |
| --- | --- | --- |
| GET | `/health` | status, which copy answered, how many points have data |
| GET | `/points?zone=3` | latest value of every point, or one zone's |
| GET | `/points/{name}/history?minutes=60` | readings for one point |
| GET | `/zones/{zone}` | latest values and faults for one zone |
| GET | `/faults?minutes=30` | faults from rules and the ML model |

Interactive docs at `/api/docs` when running behind Nginx, or `/docs` on the API directly.

## More

- [RUNBOOK.md](RUNBOOK.md): checking health and fixing common problems
- [docs/aws.md](docs/aws.md): running it on an AWS EC2 instance
- [docs/design-notes.md](docs/design-notes.md): why each choice was made
