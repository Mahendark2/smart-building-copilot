"""A fake LLM server for testing without internet or a key. It is NOT AI.

It speaks the same /v1/chat/completions API as OpenAI, Gemini and Ollama, and
follows a fixed script: ask for faults, then look at the first faulty zone,
then write an answer from what the tools returned. Use it to check that the
whole chain works; use a real model for the demo.

Run:  uvicorn scripts.mock_llm:app --port 9000
Then: LLM_PROVIDER=openai LLM_API_KEY=x LLM_BASE_URL=http://localhost:9000/v1
"""
import json
import time

from fastapi import FastAPI, Request

app = FastAPI()


def reply(message, finish):
    return {"id": f"mock-{time.time_ns()}", "object": "chat.completion", "created": int(time.time()),
            "model": "mock", "choices": [{"index": 0, "message": message, "finish_reason": finish}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}}


def call(name, args, n):
    return reply({"role": "assistant", "content": None, "tool_calls": [{
        "id": f"call_{n}", "type": "function",
        "function": {"name": name, "arguments": json.dumps(args)}}]}, "tool_calls")


@app.post("/v1/chat/completions")
async def completions(req: Request):
    body = await req.json()
    msgs = body["messages"]
    tool_msgs = [m for m in msgs if m["role"] == "tool"]

    if not tool_msgs:
        return call("get_faults", {"minutes": 30}, 1)

    if len(tool_msgs) == 1:
        faults = json.loads(tool_msgs[0]["content"]).get("faults", [])
        if faults:
            return call("get_zone", {"zone": faults[0]["zone"]}, 2)
        text = "No faults right now. All 6 zones look normal."
        return reply({"role": "assistant", "content": text}, "stop")

    faults = json.loads(tool_msgs[0]["content"])["faults"]
    zone = json.loads(tool_msgs[1]["content"])
    v = zone["values"]
    lines = [f"I found {len(faults)} fault(s)."]
    for f in faults:
        lines.append(f"Zone {f['zone']}: {f['type']} ({f['severity']}). {f['detail']}")
    lines.append(f"Zone {zone['zone']} right now: room {v.get('zone_temp')} C, damper "
                 f"{v.get('damper_pos')}%, valve {v.get('valve_pos')}%.")
    return reply({"role": "assistant", "content": "\n".join(lines)}, "stop")
