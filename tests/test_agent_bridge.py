from services import agent_bridge


class FakeAgent:
    def __init__(self):
        self.calls = []

    def get_state(self, config):
        self.calls.append(("get_state", config))
        return {"state": "ok"}

    def update_state(self, config, values):
        self.calls.append(("update_state", config, values))
        return {"updated": True}

    def invoke(self, input_data, config):
        self.calls.append(("invoke", input_data, config))
        return {"messages": []}

    def stream(self, input_data, config, stream_mode):
        self.calls.append(("stream", input_data, config, stream_mode))
        return iter(("event",))


def test_agent_bridge_delegates_graph_calls(monkeypatch):
    fake_agent = FakeAgent()
    config = {"configurable": {"thread_id": "thread-1"}}

    monkeypatch.setattr(agent_bridge, "build_agent", lambda: fake_agent)

    assert agent_bridge.get_state(config) == {"state": "ok"}
    assert agent_bridge.update_state(config, {"messages": []}) == {"updated": True}
    assert agent_bridge.invoke({"messages": []}, config) == {"messages": []}
    assert list(agent_bridge.stream(None, config, "updates")) == ["event"]

    assert [call[0] for call in fake_agent.calls] == [
        "get_state",
        "update_state",
        "invoke",
        "stream",
    ]
