"""Web endpoints: the chat page, the chat API, feedback (thumbs up/down) and a health check."""

import json
import logging
from functools import lru_cache

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.db import connection
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from agent.agent import TripAgent
from agent.llm import ClaudeLLM, FakeLLM
from agent.maps import make_maps
from agent.offline import OfflinePlanner
from src.constraints import DAYS, estimate_cost, hhmm_to_min, is_open
from src.serving import PlaceIndex

from .models import PlaceFeedback, TripLog
from .limits import bounded_endpoint, paid_mode

logger = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 8000

MAX_HISTORY = 10  # remember the last 10 messages of the conversation


@lru_cache(maxsize=1)
def get_agent():
    """Build the agent once per server process (loading the place index takes a moment)."""
    index = PlaceIndex()
    if settings.AGENT_BACKEND == "offline":
        return OfflinePlanner(index, make_maps(index))
    llm = ClaudeLLM() if settings.AGENT_BACKEND == "claude" else FakeLLM()
    return TripAgent(llm, index, make_maps(index), use_tools=True)


def index(request):
    return render(
        request,
        "planner/index.html",
        {
            "backend": settings.AGENT_BACKEND,
            "paid_mode": paid_mode(),
            "maps_mode": settings.MAPS_MODE,
        },
    )


@require_GET
def healthz(request):
    """Liveness only: no expensive model/API/data initialization."""
    return JsonResponse({"ok": True})


@require_GET
@never_cache
def readyz(request):
    """Readiness probes local artifacts, database and limiter cache. No paid API calls."""
    import uuid

    try:
        if settings.MAPS_MODE == "google":
            import os
            from pathlib import Path

            if not Path(os.environ.get("GOOGLE_PLACE_IDS_FILE", "")).is_file():
                raise RuntimeError("verified place ID mapping unavailable")
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM planner_triplog LIMIT 1")
        key = "readiness:" + uuid.uuid4().hex
        cache.set(key, "ok", 10)
        if cache.get(key) != "ok":
            raise RuntimeError("cache unavailable")
        cache.delete(key)
        from src import config

        required = [
            config.DATA_PROCESSED / "places.parquet",
            config.ARTIFACTS / "tfidf_vectorizer.joblib",
            config.ARTIFACTS / "place_tfidf.npz",
            config.ARTIFACTS / "item_stats.npz",
        ]
        if not all(path.is_file() and path.stat().st_size for path in required):
            raise RuntimeError("artifacts unavailable")
    except Exception:
        return JsonResponse({"ready": False}, status=503)
    return JsonResponse({"ready": True})


def _data_source():
    live = settings.MAPS_MODE == "google"
    return {
        "backend": settings.AGENT_BACKEND,
        "maps_mode": settings.MAPS_MODE,
        "attribution": "Google Maps" if live else None,
        "attribution_url": "https://maps.google.com" if live else None,
        "historical_catalog": True,
        "cost_basis": "heuristic estimates",
        "travel_basis": "Google route-duration estimate" if live else "distance-based estimate",
        "history_persisted": not live,
    }


def _session_payload(request):
    return {
        "authenticated": request.user.is_authenticated,
        "paid_access": bool(
            request.user.is_authenticated and request.user.is_active and request.user.is_staff
        ),
        "csrf_token": get_token(request),
        "data_source": _data_source(),
    }


@require_GET
@never_cache
@ensure_csrf_cookie
def api_session(request):
    return JsonResponse(_session_payload(request))


@require_POST
@never_cache
@bounded_endpoint("login")
def api_login(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError("invalid object")
        username, password = data.get("username"), data.get("password")
        if not isinstance(username, str) or not isinstance(password, str):
            raise ValueError("invalid credentials")
        if not username or len(username) > 150 or not password or len(password) > 1024:
            raise ValueError("invalid credentials")
    except (ValueError, TypeError):
        return JsonResponse({"error": "invalid_login_request"}, status=400)
    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "invalid_credentials"}, status=401)
    login(request, user)
    return JsonResponse(_session_payload(request))


@require_POST
@never_cache
def api_logout(request):
    logout(request)
    return JsonResponse(_session_payload(request))


class PlannerLoginView(LoginView):
    template_name = "registration/login.html"

    @method_decorator(bounded_endpoint("login"))
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


def _warnings(itinerary, prefs, idx):
    """Quick sanity checks we can do with what we know about the trip so far."""
    out = []
    day = str(prefs.get("day", "")).strip().lower()
    for stop in itinerary.get("stops", []):
        item = idx.by_id.get(stop["place_id"])
        if item is None or day not in DAYS:
            continue
        try:
            start, end = hhmm_to_min(stop["arrive"]), hhmm_to_min(stop["leave"])
        except ValueError:
            continue
        if is_open(idx.hours[item], DAYS.index(day), start, end) is False:
            out.append(
                f"{stop.get('name', 'A stop')} may be closed at {stop['arrive']} on {day.title()}."
            )
    return out


@require_POST
@never_cache
@bounded_endpoint("chat", paid_access=True)
def api_chat(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict) or not isinstance(data.get("message"), str):
            raise ValueError("message must be a string")
        message = data["message"].strip()
    except (ValueError, TypeError):
        return HttpResponseBadRequest('send JSON like {"message": "..."}')
    if not message or len(message) > MAX_MESSAGE_LENGTH:
        return HttpResponseBadRequest("message must contain 1 to 8000 characters")
    if not request.session.session_key:
        request.session.save()
    history = request.session.get("history", []) if settings.MAPS_MODE != "google" else []
    prefs = request.session.get("preferences", {}) if settings.MAPS_MODE != "google" else {}

    try:
        agent = get_agent()
        candidates = (
            None
            if settings.AGENT_BACKEND == "offline"
            else agent.index.search(message, k=10) or None
        )
        result = agent.run(
            message, request=dict(prefs), history=history, preferences=prefs, candidates=candidates
        )
    except Exception as exc:
        # Never send provider exceptions, credentials, or debug traces to the browser.
        logger.warning("Planner unavailable (%s)", type(exc).__name__)
        return JsonResponse(
            {"error": "Planner temporarily unavailable. Please try again."}, status=503
        )
    itinerary = result["itinerary"]
    stops = []
    if itinerary:
        for s in itinerary["stops"]:
            item = agent.index.by_id[s["place_id"]]
            row = agent.index.places.iloc[item]
            stops.append(
                {
                    **s,
                    "name": row["name"],
                    "categories": row["categories"],
                    "est_cost": estimate_cost(row["price"], row["categories"]),
                }
            )
    reply = result["reply"] or (
        "Here is a plan." if itinerary else "Could you tell me more about your trip?"
    )

    # keep a short text-only history so the next turn has context
    history_reply = reply
    if itinerary:
        history_reply += "\nPrevious itinerary: " + json.dumps(itinerary, ensure_ascii=False)
    history = (
        history
        + [{"role": "user", "content": message}, {"role": "assistant", "content": history_reply}]
    )[-MAX_HISTORY:]
    if settings.MAPS_MODE == "google":
        # Provider-derived summaries/hours/routes must not enter persistent logs or sessions.
        # The live endpoint is stateless between turns; supply full trip facts each time.
        request.session.pop("history", None)
        request.session.pop("preferences", None)
    else:
        request.session["history"] = history
        request.session["preferences"] = result["preferences"]
        TripLog.objects.create(
            session_key=request.session.session_key,
            user_text=message,
            reply=reply,
            itinerary=itinerary,
            tool_calls=result["tool_calls"],
        )
    return JsonResponse(
        {
            "reply": reply,
            "stops": stops,
            "history_persisted": settings.MAPS_MODE != "google",
            "data_source": _data_source(),
            "preferences": result["preferences"],
            "warnings": _warnings(itinerary, result["preferences"], agent.index)
            if itinerary
            else [],
        }
    )


@require_POST
@bounded_endpoint("feedback", paid_access=True)
def api_feedback(request):
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        pid, name, liked = data.get("place_id"), data.get("place_name", ""), data.get("liked")
        if not isinstance(pid, str) or not pid.strip() or len(pid) > 128:
            raise ValueError("invalid place id")
        if not isinstance(name, str) or len(name) > 256 or type(liked) is not bool:
            raise ValueError("invalid feedback")
        if not request.session.session_key:
            request.session.save()
        PlaceFeedback.objects.create(
            session_key=request.session.session_key,
            place_id=data["place_id"],
            place_name="" if settings.MAPS_MODE == "google" else data.get("place_name", ""),
            liked=liked,
        )
    except (ValueError, TypeError):
        return HttpResponseBadRequest("bad feedback")
    return JsonResponse({"saved": True})


@require_POST
def api_reset(request):
    request.session.pop("history", None)
    request.session.pop("preferences", None)
    return JsonResponse({"reset": True})
