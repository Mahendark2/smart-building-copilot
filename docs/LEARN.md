# Learn the Smart Building Copilot

This guide explains every part of the project in plain words, so you can run it,
demo it, and answer any question about it. Read it top to bottom once, then
keep it open while you look at the code.

---

## 1. The 30-second version

> Smart Building Copilot watches a building's heating and cooling system and
> explains problems in plain English. A simulated BACnet controller produces 72
> live HVAC readings. A gateway reads them over BACnet and saves them to
> PostgreSQL. A FastAPI backend finds faults with rules plus a machine learning
> model. A React dashboard shows everything, and an AI agent answers questions by
> calling the API as tools, so its answers come from real data, not guesses. It
> all runs in Docker, with three copies of the API behind Nginx and tests on
> every push.

Learn that paragraph so you can say it without reading.

---

## 2. The big picture

Think of the project like a hospital:

| Hospital | This project |
| --- | --- |
| The patient | The building (6 rooms, called zones) |
| Heart-rate and blood-pressure sensors | The 72 BACnet points |
| The nurse who writes readings in the chart every few minutes | The gateway |
| The patient chart | PostgreSQL |
| The doctor who reads the chart and spots problems | The API with fault detection |
| The screen above the bed | The React dashboard |
| A doctor you can ask questions, who checks the chart before answering | The AI assistant |

```
 Simulator  --BACnet/IP-->  Gateway  -->  PostgreSQL
                                              |
 Browser --> Nginx --> API copy 1, 2, 3  <----+
               |            ^
               +--> Assistant --(tool calls)--+
                        |
                        +--> LLM (Gemini, Ollama or OpenAI)
```

Seven containers run together: `db`, `simulator`, `gateway`, 3 x `api`,
`assistant`, `nginx` (plus `ollama` if you choose the local model).

---

## 3. Follow one reading from sensor to screen

This is the most common interview question: "Walk me through how data flows."

1. **The simulator makes a value.** Every 2 seconds, `sbc/model.py` moves each
   zone's numbers a little: the room warms from outside heat and cools when cold
   air comes in. Then `sbc/simulator.py` writes the new number into a BACnet
   object, for example `analog-value 101`, which is zone 1's room temperature.
2. **The gateway asks for it.** Every 5 seconds, `sbc/gateway.py` sends a BACnet
   **ReadProperty** request: "device at this address, give me the present-value
   of analog-value 101". It sends all 72 requests at the same time using Python's
   `asyncio.gather`, so one poll takes a fraction of a second.
3. **The gateway saves it.** `db.save_readings()` adds one row per point to the
   `readings` table: which point, what time, what value.
4. **The browser asks the API.** Every 5 seconds the dashboard calls
   `/api/points`. Nginx passes it to one of the 3 API copies.
5. **The API reads the latest value.** `db.latest()` finds, for each point, the
   newest row, and returns all 72 as JSON.
6. **React draws it.** `App.jsx` groups the points by zone, and `Zone.jsx` draws
   one card per zone. A zone with a fault gets a red top border.

---

## 4. Follow one question through the AI agent

Question: **"Why is zone 3 so warm?"**

1. `Chat.jsx` sends `POST /assistant/chat` with the message.
2. `assistant.py` sends the LLM three things: a system prompt (who it is, the
   rules), the question, and the list of 4 tools with a description of each.
3. The LLM does not answer yet. It replies: *call `get_zone` with `{"zone": 3}`*.
4. `run_tool()` calls the API at `/zones/3` and gets the real values and faults.
5. That result goes back to the LLM as a `tool` message.
6. The LLM may ask for another tool, for example `get_history` for
   `zone3.zone_temp` to see whether it is getting worse. That is the
   **multi-step** part.
7. When it has enough, it replies with normal text. That text is the answer, and
   the dashboard shows which tools it used, for example `get_zone → get_history`.

The loop stops after 6 steps, so a confused model cannot loop forever.

If a model is busy (Google's 503 "high demand" error) or retired (404), `ask()`
moves straight to the next model in `LLM_MODEL`. Each call gives up after 30
seconds instead of retrying for minutes, and the chat shows which model answered.

**Why tools matter:** without tools, an LLM would invent a temperature. With
tools, it can only talk about numbers it actually received.

What the messages look like (simplified):

```json
[
  {"role": "system", "content": "You are the Smart Building Copilot..."},
  {"role": "user", "content": "Why is zone 3 so warm?"},
  {"role": "assistant", "tool_calls": [{"id": "call_1", "function": {"name": "get_zone", "arguments": "{\"zone\": 3}"}}]},
  {"role": "tool", "tool_call_id": "call_1", "content": "{\"values\": {\"damper_pos\": 0, \"valve_pos\": 100, ...}}"},
  {"role": "assistant", "content": "Zone 3's damper is stuck at 0% while the cooling valve is fully open..."}
]
```

---

## 5. Every file, what it does

### Python (`sbc/`)

| File | What it does | Lines worth knowing |
| --- | --- | --- |
| `points.py` | Defines the 72 points: 6 zones x 12 kinds. Zone z's points are instances `z*100+1` to `z*100+12`. | `all_points()` builds the list once. |
| `model.py` | The fake physics. Each `Zone` has a temperature, setpoints, damper, valve, fan, CO2, humidity. `step()` moves time forward one tick. Faults change behaviour: `stuck_damper` forces the damper to 0, `sensor_drift` adds a slowly growing error to the supply-air reading. | The simple controller: `err = temp - setpoint`, then open the valve and damper more when the room is warm. |
| `simulator.py` | Turns the model into a real BACnet/IP device with BACpypes3. Creates 60 `AnalogValueObject`s and 12 `BinaryValueObject`s, then updates their `presentValue` every tick. | `make_objects()` and `push()`. |
| `gateway.py` | BACnet client. Reads every point and saves the values. | `read_all()` uses `asyncio.gather` to read all 72 at once. `controller_address()` turns the Docker name `simulator` into an IP, because BACnet needs an IP address. |
| `db.py` | Database tables and queries, with SQLAlchemy. Table `points` (one row per point) and table `readings` (one row per point per poll). | `latest()` uses a subquery: for each point, find the newest time, then join back to get that value. |
| `faults.py` | Fault detection. `rule_faults()` checks known patterns. `ml_faults()` trains an Isolation Forest. `detect()` merges both and sorts by severity. | See section 6. |
| `api.py` | FastAPI app with 5 endpoints. Adds an `X-Served-By` header so you can see which copy answered. | `lifespan()` creates the tables at startup. |
| `assistant.py` | Flask app with `/chat` and `/health`. Holds the tool list, the provider presets and the tool loop. | `chat()` is the agent loop. `run_tool()` maps tool names to API calls. |

### Front end (`web/`)

| File | What it does |
| --- | --- |
| `src/App.jsx` | Loads points and faults every 5 s with `useEffect` and `setInterval`, keeps them in `useState`, lays out the page. |
| `src/Zone.jsx` | One zone card: big room temperature plus a table of the other 11 points. |
| `src/Faults.jsx` | The fault list, coloured by severity. |
| `src/Chat.jsx` | The chat panel, example questions, and the "Tools used" line. |
| `nginx.conf` | Serves the built React files, sends `/api/` to the API copies and `/assistant/` to the assistant. |
| `vite.config.js` | During development, forwards `/api` and `/assistant` to local ports. |

### Running and testing

| File | What it does |
| --- | --- |
| `Dockerfile` | One Python image for simulator, gateway, API and assistant. Compose picks the command. |
| `web/Dockerfile` | Two stages: build React with Node, then copy the result into an Nginx image. |
| `docker-compose.yml` | Starts all services, sets their settings, runs 3 API copies (`replicas: 3`), waits for the database (`healthcheck`). |
| `.github/workflows/ci.yml` | On every push: tests on SQLite and PostgreSQL, builds React, builds every Docker image. |
| `run.py` | Plan B: starts everything in one process on one port with SQLite, no Docker. The API and assistant are mounted under `/api` and `/assistant` like Nginx does. |
| `sbc/feeder.py` | Only for `run.py --no-bacnet`: runs the same building model and writes straight to the database, skipping BACnet, for machines where UDP 47808 is blocked. |
| `tests/` | 15 tests. `conftest.py` fills a test database with 60 simulated readings with 3 faults switched on. |
| `scripts/mock_llm.py` | A fake LLM server with a fixed script. It is not AI. Use it only to test the plumbing without internet. |

---

## 6. The ideas behind it

### BACnet in one minute

BACnet is the standard language building systems use to talk, like HTTP is for
websites.

- A **device** is a controller, here the simulator (device instance 1001).
- A device holds **objects**. Each has a type and a number, for example
  `analog-value 101`. Analog means a number, binary means on or off.
- Each object has **properties**. The one we care about is `present-value`, the
  current reading.
- BACnet/IP runs over **UDP port 47808**.
- **ReadProperty** asks for one property of one object. That is what the
  gateway uses.
- **COV** (change of value) is the other option: the device tells you when a
  value changes. We poll instead because it is simpler to debug.

### Why the API is "stateless"

No API copy remembers anything between requests. Everything lives in
PostgreSQL. So any copy can answer any request, and if one crashes, the others
carry on. That is what makes running 3 copies safe.

### How Nginx finds the 3 copies

Docker Compose gives all 3 copies the same name, `api`. Docker has a built-in
DNS server at `127.0.0.1` inside every container (address `127.0.0.11`). When
Nginx asks it for `api`, it gets all 3 addresses and spreads requests across
them. `resolver ... valid=10s` makes Nginx ask again every 10 seconds, so a
restarted copy is found. Proof: call `/api/health` a few times and watch
`X-Served-By` change.

### The fault rules

| Rule | Plain meaning |
| --- | --- |
| Stuck damper | The system is asking for cooling (valve over 80% open), the room is hot, but the air gate is closed (under 5%). The gate must be stuck. |
| Fan off while occupied | People are in the room but no air is moving. |
| Supply sensor drift | This zone's supply-air reading pulls away from the building's median supply-air reading by over 0.5 C across 30 readings, while its valve has not changed. Comparing with the median means a change that hits every zone at once (a restart, a hot afternoon) is not mistaken for drift. |
| High CO2 | Over 1000 ppm means stale air, not enough ventilation. |

### The machine learning part: Isolation Forest

Imagine you play "guess the number" with a stranger. Normal readings sit in a
big crowd, so it takes many yes/no questions to single one out. A weird reading
sits alone, so a few questions isolate it.

An Isolation Forest asks random yes/no questions ("is the damper below 37%?")
and counts how many it takes to isolate each reading. Readings isolated quickly
are outliers. We build 150 of these random question trees and average them.

Why it fits here:
- It needs no labelled examples of faults, and we have none.
- It trains in milliseconds, so it retrains on every request on the last 30
  minutes.
- It catches faults no rule describes, because it just asks "which zone looks
  unlike the others?"

Features used per reading: distance from setpoint, supply air temperature,
damper, valve, fan speed, CO2. They are scaled first so no single number
dominates. The model is told to expect about 10% outliers (`contamination=0.1`).
A zone is flagged only when all of its last 5 readings are outliers, so one odd
reading does not raise an alarm. If a rule already caught that zone, the ML
result is hidden to avoid repeating it.

### Tool calling, in one minute

You describe your functions to the LLM in JSON: name, what it does, what
arguments it takes. The LLM cannot run them. It can only reply "please run
`get_zone` with zone 3". Your code runs it and sends back the result. This is
how agents connect to real systems.

### "OpenAI-compatible"

OpenAI's chat API shape became the standard. Gemini, Ollama, Groq and vLLM all
accept it. So the same code works with any of them: only the address and model
name change. That is the `PROVIDERS` table in `assistant.py`.

### Why FastAPI for the API and Flask for the assistant?

FastAPI checks inputs by their types and writes interactive docs at `/docs`
for free, which suits an API with several endpoints. The assistant is one
endpoint that mostly waits on the LLM, so plain Flask with Gunicorn is enough.

### How the agent is tested without a real LLM

`tests/test_assistant.py` uses a fake LLM object that always asks for faults,
then zone 3, then answers. The test checks the tools ran in that order and that
the answer used the real damper value. That proves the loop works without
paying for API calls, and CI can run it on every push.

---

## 7. Run it on your laptop

### One time setup

1. **Install Docker Desktop** from docker.com and start it. On Windows, accept
   the WSL 2 setup it offers and restart.
2. **Get a free Gemini key** at https://aistudio.google.com/apikey (sign in
   with Google, click Create API key).
3. Unzip the project, open a terminal in the folder, and run:
   ```bash
   cp .env.example .env
   ```
   (Windows PowerShell: `copy .env.example .env`)
4. Open `.env` and paste your key after `LLM_API_KEY=`.

### Start

```bash
docker compose up --build
```

The first build takes a few minutes. When you see `gateway ... saved 72/72
points`, open **http://localhost:8080**.

Wait about 1 minute for the first faults and about 3 minutes for sensor drift
(it needs 30 readings).

### Check it is healthy

```bash
curl localhost:8080/api/health           # status ok, 72 points
curl localhost:8080/assistant/health     # llm_configured true
curl -si localhost:8080/api/health | grep X-Served-By   # run 3 times, name changes
```

### No key? Use the local model

Set `LLM_PROVIDER=ollama` in `.env`, leave the key empty, then:

```bash
docker compose --profile local-llm up --build
```

It downloads the `qwen2.5:3b` model (about 2 GB) the first time. It needs about
4 GB of free RAM and answers slower than Gemini.

### Stop

`Ctrl+C`, then `docker compose down`. Your readings are kept. `docker compose
down -v` deletes them.

If something breaks, see [../RUNBOOK.md](../RUNBOOK.md).

### Plan B: one command, no Docker

Use this if Docker gives you trouble. You only need Python 3.12 or 3.13.

```bash
pip install -r requirements.txt
python run.py
```

Open **http://localhost:8080**. It runs the real BACnet simulator and gateway,
uses SQLite instead of PostgreSQL, and serves the dashboard, API and assistant
on one port. It reads your `.env` the same way and prints which LLM it is using.

- BACnet or socket errors on Windows: `python run.py --no-bacnet`.
- Local model without Docker: install Ollama from ollama.com, run
  `ollama pull qwen2.5:3b`, and set `LLM_PROVIDER=ollama` in `.env`.

What Plan B leaves out: the 3 API copies behind Nginx and PostgreSQL. So for
the demo, Docker is better; Plan B is your backup if Docker fails on the day.

---

## 8. A 5-minute demo

1. **The pitch (30 s).** Say the 30-second version from section 1.
2. **The dashboard (1 min).** Show the 6 zone cards updating. Point at zone 3:
   damper 0%, valve 100%, room much hotter than its setpoint. Point at the
   fault list and say which came from rules and which from ML.
3. **Ask the agent (2 min).**
   - "Are there any faults right now?" Show the "Tools used" line.
   - "Why is zone 3 so warm?" It should mention the stuck damper with real numbers.
   - "How has the zone 5 supply air temperature changed in the last 30 minutes?"
     It should call `get_history` and describe the rise.
4. **Under the hood (1 min).** Run `curl -si localhost:8080/api/health` twice and
   show `X-Served-By` changing: 3 stateless copies behind Nginx. Open
   `localhost:8080/api/docs` to show the API.
5. **Quality (30 s).** Show the GitHub Actions run: tests on SQLite and
   PostgreSQL, React build, Docker build.

Practise it twice before the interview.

---

## 9. Questions you will likely get

**Is the data real?**
No. It comes from a simulated BACnet controller I wrote with BACpypes3. It
speaks real BACnet/IP, so the gateway would work with a real controller by
changing one address.

**Why poll every 5 seconds instead of COV?**
Simpler and easy to debug. COV would cut traffic and is my next step for a
larger building.

**How do you get the latest value for each point?**
A subquery finds the newest timestamp per point, then I join back to the
readings table to get the value at that time.

**What happens if one API copy dies?**
Nginx skips it (`proxy_next_upstream`) and Docker restarts it. Users do not
notice, because no copy holds state.

**Why Isolation Forest and not a neural network?**
No labelled fault data, small data, needs to be explainable and fast. Isolation
Forest fits all four.

**How do you stop the LLM from making things up?**
The system prompt says to always use tools for numbers, and the tools return
real data. The tool steps are shown in the UI, so a user can see where the
answer came from.

**What if the model calls tools forever?**
The loop stops after 6 steps and says so.

**Why summarise history before sending it to the model?**
Hundreds of rows waste tokens and slow the answer. First, last, min, max and the
last 10 readings are enough to describe a trend.

**How would you scale this to 10,000 points?**
COV subscriptions instead of polling, batch inserts, a time-series extension
such as TimescaleDB, and precomputing faults on a schedule instead of on each
request.

**What was hard?**
Running the simulator and gateway on one machine: both wanted UDP port 47808,
and the gateway ended up answering its own requests. Giving the gateway its own
port, 47809, fixed it. In Docker each has its own IP, so both use 47808.

**What would you add next?**
Writing setpoints back over BACnet with a confirm step, storing fault history so
the agent can say when a problem started, and a job that trims old readings.

**Did you use AI tools to build it?**
Answer honestly. A good answer: "Yes, I used AI coding tools, the same way teams
do now. I designed the parts, tested each one, and I can explain every file."
Then prove it by explaining any file they pick.

---

## 10. Honest limits

- The building is simulated, and so are the faults.
- Fault thresholds were picked to fit the simulator, not tuned on a real building.
- There is no login. Anyone who can reach the page can use it.
- The ML model retrains on every request, which is fine for 72 points, not for
  thousands.

Saying these out loud in an interview shows you understand the project.
