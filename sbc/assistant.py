"""Flask LLM assistant. It talks to any OpenAI-compatible model and answers
questions by calling tools that hit the building API.

Run:  flask --app sbc.assistant run --port 5000
Env:  LLM_API_KEY, LLM_BASE_URL (optional), LLM_MODEL, API_URL
"""
import json
import os

import requests
from flask import Flask, jsonify, request

API_URL = os.getenv("API_URL", "http://localhost:8000")
MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
MAX_STEPS = int(os.getenv("MAX_TOOL_STEPS", "6"))

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
    key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    return OpenAI(api_key=key, base_url=os.getenv("LLM_BASE_URL") or None)


def chat(messages, client):
    """Multi-step tool loop: the model can call several tools, one after
    another, until it has what it needs to answer."""
    msgs = [{"role": "system", "content": SYSTEM}] + messages
    steps = []
    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(model=MODEL, messages=msgs, tools=TOOLS)
        msg = resp.choices[0].message
        if not msg.tool_calls:
            return {"answer": msg.content, "steps": steps}

        msgs.append({"role": "assistant", "content": msg.content or "",
                     "tool_calls": [{"id": t.id, "type": "function",
                                     "function": {"name": t.function.name,
                                                  "arguments": t.function.arguments}}
                                    for t in msg.tool_calls]})
        for t in msg.tool_calls:
            args = json.loads(t.function.arguments or "{}")
            result = run_tool(t.function.name, args)
            steps.append({"tool": t.function.name, "args": args})
            msgs.append({"role": "tool", "tool_call_id": t.id, "content": json.dumps(result)})

    return {"answer": "I needed too many steps to answer that. Try a more specific question.",
            "steps": steps}


app = Flask(__name__)


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": bool(os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY"))}


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
        return jsonify(error="LLM not configured. Set LLM_API_KEY (and LLM_BASE_URL for "
                             "a non-OpenAI provider)."), 503
    try:
        return jsonify(chat(messages[-12:], client))
    except Exception as e:
        return jsonify(error=f"LLM call failed: {e}"), 502
