"""Tests the tool loop with a fake LLM, so no API key is needed."""
import json
from types import SimpleNamespace as NS

from fastapi.testclient import TestClient

from sbc import api, assistant

api_client = TestClient(api.app)


def fake_call_api(path, params=None):
    r = api_client.get(path, params=params)
    r.raise_for_status()
    return r.json()


def tool_call(i, name, args):
    return NS(id=f"call_{i}", function=NS(name=name, arguments=json.dumps(args)))


class FakeLLM:
    """Asks for faults, then for zone 3, then answers using what it got back."""

    def __init__(self):
        self.calls = 0
        self.seen = []
        self.chat = NS(completions=NS(create=self.create))

    def create(self, model, messages, tools):
        self.calls += 1
        self.seen.append(messages[-1])
        if self.calls == 1:
            msg = NS(content=None, tool_calls=[tool_call(1, "get_faults", {})])
        elif self.calls == 2:
            msg = NS(content=None, tool_calls=[tool_call(2, "get_zone", {"zone": 3})])
        else:
            zone = json.loads(messages[-1]["content"])
            damper = zone["values"]["damper_pos"]
            msg = NS(content=f"Zone 3 damper is at {damper}%. Check the actuator.", tool_calls=None)
        return NS(choices=[NS(message=msg)])


def test_multi_step_tool_calling(filled_db, monkeypatch):
    monkeypatch.setattr(assistant, "call_api", fake_call_api)
    llm = FakeLLM()
    out = assistant.chat([{"role": "user", "content": "Any problems?"}], llm)

    assert [s["tool"] for s in out["steps"]] == ["get_faults", "get_zone"]
    assert "damper is at 0" in out["answer"]
    faults = json.loads(llm.seen[1]["content"])["faults"]
    assert any(f["type"] == "stuck_damper" for f in faults)


def test_history_tool_is_summarised(filled_db, monkeypatch):
    monkeypatch.setattr(assistant, "call_api", fake_call_api)
    data = assistant.run_tool("get_history", {"name": "zone5.supply_air_temp", "minutes": 60})
    assert data["summary"]["count"] == 60
    assert len(data["readings"]) == 10


def test_chat_route_without_key(monkeypatch):
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    r = assistant.app.test_client().post("/chat", json={"question": "hi"})
    assert r.status_code == 503
