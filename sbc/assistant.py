"""Flask LLM assistant. It talks to any OpenAI-compatible model and answers
questions by calling tools that hit the building API.

Run:  flask --app sbc.assistant run --port 5000
Env:  LLM_PROVIDER (gemini, ollama, openai), LLM_API_KEY, API_URL
      LLM_BASE_URL and LLM_MODEL override the provider's defaults.
"""
import json
import os

import requests
from flask import Flask, jsonify, request

API_URL = os.getenv("API_URL", "http://localhost:8000")
MAX_STEPS = int(os.getenv("MAX_TOOL_STEPS", "6"))

# All three speak the same OpenAI chat API, so only the address and model change.
PROVIDERS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "model": "gemini-2.5-flash"},
    "ollama": {"base_url": "http://ollama:11434/v1", "model": "qwen2.5:3b"},
    "openai": {"base_url": None, "model": "gpt-4o-mini"},
}


def settings():
    name = (os.getenv("LLM_PROVIDER") or "gemini").lower()
    p = PROVIDERS.get(name, PROVIDERS["openai"])
    return {
        "provider": name,
        "base_url": os.getenv("LLM_BASE_URL") or p["base_url"],
        "model": os.getenv("LLM_MODEL") or p["model"],
        # Ollama runs on your machine and needs no key, but the client wants a string
        "key": os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ("ollama" if name == "ollama" else None),
    }

SYSTEM = """You are the Smart Building Copilot, an assistant for facility staff.
The building has 6 zones, each with 12 HVAC points (temperatures, setpoints,
damper, valve, fan, CO2, humidity, occupancy). The data comes from a simulated
BACnet controller.
Always use the tools to get real numbers before answering. Never guess a value.
Keep answers short and practical. When there is a fault, say what it is, which
zone, the evidence, and what a technician should check first."""

TOOLS = [
    {"type": "function", "function": {
        "name": "get_faults",
        "description": "List active faults found by rules and the ML model.",
        "parameters": {"type": "object", "properties": {
            "minutes": {"type": "integer", "description": "How far back to look. Default 30."}}}}},
    {"type": "function", "function": {
        "name": "get_zone",
        "description": "Latest values and faults for one zone.",
        "parameters": {"type": "object", "properties": {
            "zone": {"type": "integer", "description": "Zone number 1 to 6."}},
            "required": ["zone"]}}},
    {"type": "function", "function": {
        "name": "get_points",
        "description": "Latest value of every point, or of one zone's points.",
        "parameters": {"type": "object", "properties": {
            "zone": {"type": "integer"}}}}},
    {"type": "function", "function": {
        "name": "get_history",
        "description": "Recent readings for one point, e.g. zone3.zone_temp.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "minutes": {"type": "integer"}},
            "required": ["name"]}}},
]


def call_api(path, params=None):
    r = requests.get(f"{API_URL}{path}", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def run_tool(name, args):
    try:
        if name == "get_faults":
            return call_api("/faults", {"minutes": args.get("minutes", 30)})
        if name == "get_zone":
            return call_api(f"/zones/{int(args['zone'])}")
        if name == "get_points":
            return call_api("/points", {"zone": args["zone"]} if "zone" in args else None)
        if name == "get_history":
            data = call_api(f"/points/{args['name']}/history", {"minutes": args.get("minutes", 30)})
            r = data["readings"]
            # send a summary, not hundreds of rows
            vals = [x["value"] for x in r]
            if vals:
                data["summary"] = {"count": len(vals), "first": vals[0], "last": vals[-1],
                                   "min": min(vals), "max": max(vals)}
            data["readings"] = r[-10:]
            return data
        return {"error": f"unknown tool {name}"}
    except Exception as e:
        return {"error": str(e)}


def make_client():
    from openai import OpenAI
    s = settings()
    if not s["key"]:
        return None
    return OpenAI(api_key=s["key"], base_url=s["base_url"], timeout=90)


def chat(messages, client, model=None):
    """Multi-step tool loop: the model can call several tools, one after
    another, until it has what it needs to answer."""
    msgs = [{"role": "system", "content": SYSTEM}] + messages
    steps = []
    model = model or settings()["model"]
    for step in range(MAX_STEPS):
        resp = client.chat.completions.create(model=model, messages=msgs, tools=TOOLS)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"answer": msg.content or "", "steps": steps}

        # some providers leave the id empty, so make one up
        calls = [(t.id or f"call_{step}_{i}", t) for i, t in enumerate(msg.tool_calls)]
        msgs.append({"role": "assistant", "content": msg.content or "",
                     "tool_calls": [{"id": cid, "type": "function",
                                     "function": {"name": t.function.name,
                                                  "arguments": t.function.arguments or "{}"}}
                                    for cid, t in calls]})
        for cid, t in calls:
            try:
                args = json.loads(t.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            result = run_tool(t.function.name, args)
            steps.append({"tool": t.function.name, "args": args})
            msgs.append({"role": "tool", "tool_call_id": cid, "content": json.dumps(result)})

    return {"answer": "I needed too many steps to answer that. Try a more specific question.",
            "steps": steps}


app = Flask(__name__)


@app.get("/health")
def health():
    s = settings()
    return {"status": "ok", "provider": s["provider"], "model": s["model"],
            "llm_configured": bool(s["key"])}


@app.post("/chat")
def chat_route():
    body = request.get_json(silent=True) or {}
    messages = body.get("messages")
    if not messages and body.get("question"):
        messages = [{"role": "user", "content": body["question"]}]
    if not messages:
        return jsonify(error="send a question or messages"), 400

    client = make_client()
    if client is None:
        return jsonify(error="LLM not configured. Set LLM_API_KEY in .env, or use "
                             "LLM_PROVIDER=ollama for a local model with no key."), 503
    try:
        return jsonify(chat(messages[-12:], client))
    except Exception as e:
        return jsonify(error=f"LLM call failed: {e}"), 502
