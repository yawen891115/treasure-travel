"""Check an itinerary against the trip's hard constraints. This is the judge for the evaluation.

An itinerary 'violates constraints' if it has at least one of:
  unknown_place  a place_id that is not in our catalog
  bad_time       times outside the trip window, or a stop that ends before it starts / overlaps
  closed         the place is closed during the planned visit
  travel_time    not enough time to get from the previous stop (or the start point) to this one
  leg_too_long   a single leg is longer than the traveler allowed
  over_budget    estimated total cost for the group is above the budget
"""

from src.constraints import estimate_cost, hhmm_to_min, is_open

SLACK_MIN = 5  # tolerate small timing differences


def validate(itinerary, request, index, maps):
    problems = []
    stops = (itinerary or {}).get("stops") or []
    if not stops:
        return [{"type": "empty", "detail": "no stops"}]
    day_start, day_end = hhmm_to_min(request["start"]), hhmm_to_min(request["end"])
    prev_end, prev_loc = None, (request["origin"]["lat"], request["origin"]["lng"])
    total = 0.0
    for i, stop in enumerate(stops):
        pid = stop.get("place_id")
        if pid not in index.by_id:
            problems.append({"type": "unknown_place", "stop": i, "detail": str(pid)})
            continue
        item = index.by_id[pid]
        row = index.places.iloc[item]
        try:
            arrive, leave = hhmm_to_min(stop["arrive"]), hhmm_to_min(stop["leave"])
        except (KeyError, ValueError):
            problems.append({"type": "bad_time", "stop": i, "detail": "missing or unreadable time"})
            continue
        if arrive < day_start or leave > day_end or leave <= arrive:
            problems.append(
                {"type": "bad_time", "stop": i, "detail": f"{stop['arrive']}-{stop['leave']}"}
            )
        if prev_end is not None and arrive < prev_end:
            problems.append({"type": "bad_time", "stop": i, "detail": "overlaps the previous stop"})
        day = request["weekday"]
        today = maps.opening_hours(pid, day)  # None = unknown, [] = closed all day
        known = (
            {}
            if today is None
            else {day: today, (day - 1) % 7: maps.opening_hours(pid, (day - 1) % 7) or []}
        )
        status = is_open(known, day, arrive, leave)
        if status is None:
            problems.append({"type": "unknown_hours", "stop": i, "detail": row["name"]})
        if status is False:
            problems.append({"type": "closed", "stop": i, "detail": row["name"]})
        loc = (float(row["lat"]), float(row["lng"]))
        minutes = maps.travel_minutes(prev_loc, loc, request["mode"])
        gap = arrive - (prev_end if prev_end is not None else day_start)
        if minutes > gap + SLACK_MIN:
            problems.append(
                {"type": "travel_time", "stop": i, "detail": f"needs {minutes} min, has {gap}"}
            )
        if minutes > request["max_leg_minutes"] + SLACK_MIN:
            problems.append({"type": "leg_too_long", "stop": i, "detail": f"{minutes} min"})
        total += estimate_cost(row["price"], row["categories"]) * request["group_size"]
        prev_end, prev_loc = leave, loc
    if total > request["budget"]:
        problems.append({"type": "over_budget", "detail": f"${total:.0f} > ${request['budget']}"})
    return problems
