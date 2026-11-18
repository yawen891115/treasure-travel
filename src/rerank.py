"""Constraint-aware re-ranking: push places that are closed or too far down the list."""

from src.constraints import estimate_travel_minutes, is_open, parse_hours


class PlaceConstraints:
    """Pre-parses opening hours once so checks are fast."""

    def __init__(self, places):
        self.lat = places["lat"].to_numpy()
        self.lng = places["lng"].to_numpy()
        self.hours = [parse_hours(h) for h in places["hours"]]

    def violation(self, item, weekday, start_min, visit_min, origin, max_travel_min, mode="walk"):
        """Return None if the place fits the trip, else a short reason."""
        status = is_open(self.hours[item], weekday, start_min, start_min + visit_min)
        if status is None:
            return "unknown_hours"
        if status is False:
            return "closed"
        travel = estimate_travel_minutes(origin[0], origin[1], self.lat[item], self.lng[item], mode)
        if travel > max_travel_min:
            return "too_far"
        return None


def rerank(
    ranked_items,
    constraints,
    weekday,
    start_min,
    visit_min,
    origin,
    max_travel_min,
    k=5,
    mode="walk",
):
    """Keep the model's order, but skip places that break a constraint. Returns the new top-k."""
    if k <= 0:
        return []
    kept = []
    for item in ranked_items:
        if item < 0 or item >= len(constraints.lat):
            continue
        if (
            constraints.violation(item, weekday, start_min, visit_min, origin, max_travel_min, mode)
            is None
        ):
            kept.append(item)
            if len(kept) == k:
                break
    return kept
