"""Checks the real ClaudeLLM + agent loop against a tiny local mock of the Messages API.

No network and no cost: the Anthropic SDK is pointed at http://127.0.0.1 and gets canned replies.
This proves tool calls, tool results (and thinking blocks) are sent back in the right format.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from src import config

REQUESTS = []


def _reply(content, stop):
    return {
        "id": f"msg_{len(REQUESTS)}",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": content,
        "stop_reason": stop,
        "stop_sequence": None,
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


class MockAPI(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQUESTS.append(body)
        last = body["messages"][-1]["content"]
        if len(REQUESTS) == 1:
            thinking = {"type": "thinking", "thinking": "search first", "signature": "sig1"}
            out = _reply(
                [
                    thinking,
                    {
                        "type": "tool_use",
                        "id": "toolu_1",
                        "name": "search_places",
                        "input": {"query": "art museum"},
                    },
                ],
                "tool_use",
            )
        else:
            pid = json.loads(last[0]["content"])["places"][0]["place_id"]
            out = _reply(
                [
                    {"type": "text", "text": "Done."},
                    {
                        "type": "tool_use",
                        "id": "toolu_2",
                        "name": "submit_itinerary",
                        "input": {
                            "stops": [{"place_id": pid, "arrive": "10:30", "leave": "11:30"}],
                            "summary": "One museum.",
                        },
                    },
                ],
                "tool_use",
            )
        data = json.dumps(out).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture()
def mock_api(monkeypatch):
    if not (config.ARTIFACTS / "item_stats.npz").exists():
        pytest.skip("run the pipeline on FAKE data first")
    server = HTTPServer(("127.0.0.1", 0), MockAPI)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("LLM_MODEL", "claude-haiku-5-5")
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        monkeypatch.delenv(name, raising=False)
    REQUESTS.clear()
    yield
    server.shutdown()


def test_agent_round_trip_with_sdk(mock_api):
    from agent.agent import TripAgent
    from agent.llm import ClaudeLLM
    from agent.maps import OfflineMaps
    from src.serving import PlaceIndex

    index = PlaceIndex()
    agent = TripAgent(ClaudeLLM(), index, OfflineMaps(index))
    out = agent.run("Saturday, art museums, 1 stop")
    assert out["itinerary"]["stops"][0]["arrive"] == "10:30"
    assert out["tool_calls"] == ["search_places", "submit_itinerary"]
    second = REQUESTS[1]
    assert second["model"] == "claude-haiku-5-5" and second["tools"]
    assistant, user = second["messages"][1], second["messages"][2]
    assert assistant["role"] == "assistant"
    assert assistant["content"][0] == {
        "type": "thinking",
        "thinking": "search first",
        "signature": "sig1",
    }
    result = user["content"][0]
    assert result["type"] == "tool_result" and result["tool_use_id"] == "toolu_1"
