"""The trip-planning agent: an LLM that calls tools in a loop until it submits a plan."""

import json

from agent.tools import ALL_TOOLS, SUBMIT, ToolBox, tool_result_text

RULES_WITH_TOOLS = """You are Treasure Travel's trip planner.
Build a realistic one-day plan that fits the traveler. Rules:
- Use only places from the candidate list or from search_places results, by their place_id.
- Before submitting: call get_opening_hours for every stop on the trip day,
  get_travel_time from 'start' to the first stop and between consecutive stops,
  and check_budget for the whole plan.
- Leave enough time between stops to travel. Keep every leg within the traveler's limit.
- If a place is closed, too far or too expensive, replace it
  (search_places can find alternatives nearby).
- When the traveler tells you about the trip (group, budget, interests...),
  save it with update_trip_preferences.
- Finish by calling submit_itinerary exactly once. Times are 24-hour HH:MM."""

RULES_NO_TOOLS = """You are Treasure Travel's trip planner.
Build a realistic one-day plan that fits the traveler.
Use only places from the candidate list, by their place_id.
Finish by calling submit_itinerary exactly once. Times are 24-hour HH:MM."""


def candidates_text(places):
    lines = [
        f"- {p['name']} | id={p['place_id']} | {p['categories']} | price {p['price_level']} | "
        f"~${p['est_cost_per_person']}/person"
        for p in places
    ]
    return "Candidate places from our recommender:\n" + "\n".join(lines)


class TripAgent:
    def __init__(self, llm, index, maps, use_tools=True, max_steps=16):
        self.llm, self.index, self.maps = llm, index, maps
        self.use_tools, self.max_steps = use_tools, max_steps

    def run(self, user_text, request=None, history=None, preferences=None, candidates=None):
        """One user turn. Returns dict with itinerary, reply text, updated preferences and usage."""
        box = ToolBox(self.index, self.maps, request=request, preferences=preferences)
        tools = ALL_TOOLS if self.use_tools else [SUBMIT]
        system = RULES_WITH_TOOLS if self.use_tools else RULES_NO_TOOLS
        if box.preferences:
            system += "\nShared trip preferences so far: " + json.dumps(box.preferences)
        content = user_text if not candidates else user_text + "\n\n" + candidates_text(candidates)
        messages = list(history or []) + [{"role": "user", "content": content}]
        usage = {"input_tokens": 0, "output_tokens": 0}
        reply, steps = "", 0
        for steps in range(1, self.max_steps + 1):
            resp = self.llm.respond(system, messages, tools)
            usage["input_tokens"] += resp.usage.input_tokens
            usage["output_tokens"] += resp.usage.output_tokens
            messages.append({"role": "assistant", "content": resp.content})
            texts = [b.text for b in resp.content if b.type == "text" and b.text]
            reply = "\n".join(texts) or reply
            calls = [b for b in resp.content if b.type == "tool_use"]
            if not calls:  # the model answered in words (e.g. asked a question)
                break
            results = []
            for c in calls:
                if box.submitted is not None:
                    result = {"error": "ignored after accepted itinerary"}
                else:
                    result = box.run(c.name, c.input)
                results.append({"type": "tool_result", "tool_use_id": c.id,
                                "content": tool_result_text(result)})
            messages.append({"role": "user", "content": results})
            if box.submitted is not None:  # plan accepted -> done
                reply = box.submitted.get("summary") or reply
                break
        return {
            "itinerary": box.submitted,
            "reply": reply,
            "preferences": box.preferences,
            "tool_calls": box.calls,
            "steps": steps,
            "usage": usage,
            "messages": messages,
        }
