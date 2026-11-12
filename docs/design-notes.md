# Design notes

Why each part is built the way it is, in plain words.

## Why a simulated controller?

Real BACnet controllers are expensive and sit inside real buildings. The
simulator speaks real BACnet/IP, so the gateway code is the same code you would
point at a real controller. Only the address changes.

## Why BACpypes3?

It is the main Python BACnet library, it is async (so the gateway can read all
72 points at the same time), and it can act as both a device and a client.

## Why read with ReadProperty instead of COV subscriptions?

Polling every 5 seconds is simple and easy to debug: if a read fails, the log
says which point. COV (change of value) would cut network traffic, and is the
next step if the building had thousands of points.

## Why does the API keep no state?

Every request reads from PostgreSQL. No copy remembers anything between
requests, so Nginx can send any request to any copy, and one copy can crash
without users noticing. That is why 3 copies can run side by side.

## How does Nginx find the 3 copies?

Docker Compose gives all 3 copies the same name, `api`. Docker's DNS answers
that name with all 3 addresses. Nginx asks Docker's DNS (`127.0.0.11`) and
re-asks every 10 seconds, so a restarted copy with a new address is picked up.

## Why rules and an ML model?

Rules are clear and explainable: "damper shut while valve wide open" is exactly
what a technician would check. But rules only catch faults someone thought of.
The Isolation Forest compares every zone with the others and flags one that
looks different, even when no rule matches. If a rule already flagged a zone,
the ML result is hidden so the list does not repeat itself.

## Why compare drift with the rest of the building?

The first version flagged healthy zones after a restart, because every zone's
supply temperature settles at the same time. A real drifting sensor moves away
from the others, so the rule now looks at the gap between a zone and the
building's median. Things that hit every zone at once cancel out.
`tests/test_faults.py` checks both cases.

## Why does ML need 5 odd readings in a row?

With one odd reading, healthy zones were flagged now and then, which teaches
operators to ignore alarms. Needing all of the last 5 readings to look unusual
removed those false alarms in testing, while the faulty zone was still caught.

## Why Isolation Forest?

It needs no labelled fault data (we have none), trains in milliseconds on a few
thousand rows, and works well when faults are rare and look unlike normal data.
It retrains on each request, so it always reflects the last 30 minutes.

## How does the agent work?

1. The assistant sends the question, a short system prompt, and 4 tool
   descriptions (get_faults, get_zone, get_points, get_history) to the LLM.
2. If the LLM asks for a tool, the assistant calls the API and sends the result
   back.
3. The LLM can ask for more tools: for example faults first, then the details of
   the zone with the fault. That is the multi-step part.
4. When it stops asking for tools, its reply is the answer. There is a limit of
   6 steps so a confused model cannot loop forever.

The system prompt tells it to always use tools for numbers, so it answers from
real data instead of guessing. History is summarised (first, last, min, max)
before it goes to the model, to keep the prompt small.

## Why Flask for the assistant and FastAPI for the API?

The API has many typed endpoints and benefits from FastAPI's validation and
auto docs. The assistant is one endpoint that mostly waits on the LLM, so Flask
with Gunicorn workers is simple and enough.

## Why OpenAI-compatible?

Most providers (OpenAI, Groq, Together, Ollama, vLLM) use the same API shape,
so changing provider is one setting, `LLM_BASE_URL`.

## How is the agent tested without paying for an LLM?

`tests/test_assistant.py` uses a fake LLM that asks for faults, then for zone 3,
then answers. The test checks the tools ran in that order and that the answer
used the real data. CI runs it on every push.

## What I would add next

- COV subscriptions instead of polling
- Writing setpoints back over BACnet, with a confirm step for safety
- Storing fault history, so the agent can say "this started 2 hours ago"
- A retention job that trims old readings
