"""LLM clients. ClaudeLLM calls the real API; FakeLLM is a scripted stand-in for tests."""

import os
import re
from dataclasses import dataclass, field


class ClaudeLLM:
    """Thin wrapper around the Anthropic Messages API (reads ANTHROPIC_API_KEY)."""

    def __init__(self, model=None, max_tokens=4096):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model or os.environ.get("LLM_MODEL")
        if not self.model:
            raise ValueError("Set LLM_MODEL to a model ID available in your Anthropic account")
        self.max_tokens = max_tokens

    def respond(self, system, messages, tools):
        kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
        return self.client.messages.create(**kwargs)


# ---------------------------------------------------------------- fake model for tests
@dataclass
class Block:
    type: str
    text: str = ""
    id: str = ""
    name: str = ""
    input: dict = field(default_factory=dict)


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass
class Response:
    content: list
    stop_reason: str
    usage: Usage = field(default_factory=Usage)


class FakeLLM:
    """Plans without any AI: search (if needed) -> check hours -> drop closed places -> submit.

    Good enough to test the agent loop, the website and the evaluation script for free.
    """

    def __init__(self):
        self.n = 0

    def _id(self):
        self.n += 1
        return f"toolu_fake_{self.n}"

    def respond(self, system, messages, tools):
        names = {t["name"] for t in tools}
        turn_start = max(
            i
            for i, m in enumerate(messages)
            if m["role"] == "user" and isinstance(m["content"], str)
        )
        text = messages[turn_start]["content"]
        used, results = set(), []
        for m in messages[turn_start + 1 :]:
            for b in m["content"]:
                if getattr(b, "type", None) == "tool_use":
                    used.add(b.name)
                elif isinstance(b, dict) and b.get("type") == "tool_result":
                    results.append(b["content"])
        ids = re.findall(r"id=(\S+)", text)
        for r in results:
            ids += re.findall(r'"place_id": "([^"]+)"', r)
        ids = list(dict.fromkeys(ids))  # unique, keep order
        day = (
            re.search(r"on (\w+day)", text) or re.search(r"(\w+day)", text) or [None, "Saturday"]
        )[1]
        start = (
            re.search(r"from (\d{1,2}:\d{2})", text)
            or re.search(r"(\d{1,2}:\d{2})", text)
            or [None, "10:00"]
        )[1]
        n_stops = int((re.search(r"(\d) stops", text) or [None, 3])[1])

        if not ids and "search_places" in names and "search_places" not in used:
            return Response(
                [
                    Block(
                        "tool_use", id=self._id(), name="search_places", input={"query": text[:200]}
                    )
                ],
                "tool_use",
            )
        if ids and "get_opening_hours" in names and "get_opening_hours" not in used:
            return Response(
                [
                    Block(
                        "tool_use",
                        id=self._id(),
                        name="get_opening_hours",
                        input={"place_id": i, "day": day},
                    )
                    for i in ids[:8]
                ],
                "tool_use",
            )
        closed = {
            re.search(r'"place_id": "([^"]+)"', r)[1] for r in results if '"hours": "Closed"' in r
        }
        chosen = [i for i in ids if i not in closed][:n_stops]
        if not chosen:
            return Response(
                [
                    Block(
                        "text", text="Which kinds of places do you enjoy? (e.g. art, coffee, parks)"
                    )
                ],
                "end_turn",
            )
        h, m = map(int, start.split(":"))
        t = h * 60 + m + 30
        stops = []
        for pid in chosen:
            stops.append(
                {
                    "place_id": pid,
                    "arrive": f"{t // 60:02d}:{t % 60:02d}",
                    "leave": f"{(t + 60) // 60:02d}:{(t + 60) % 60:02d}",
                }
            )
            t += 90
        submit = Block(
            "tool_use",
            id=self._id(),
            name="submit_itinerary",
            input={
                "stops": stops,
                "summary": f"A {len(stops)}-stop plan (fake planner, for testing).",
            },
        )
        return Response([Block("text", text="Here is your plan."), submit], "tool_use")
