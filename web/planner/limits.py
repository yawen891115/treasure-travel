"""Admission controls: atomic shared Redis leases, local-only fallback for development.

Leases outlive the production sync worker timeout. A crashed worker releases its
slot by expiry; normal release removes only its unique token (never a newer lease).
"""

import hashlib
import threading
import time
import uuid
from collections import defaultdict, deque
from functools import lru_cache, wraps

from django.conf import settings
from django.http import JsonResponse


class Rejected(Exception):
    def __init__(self, reason, retry_after=60):
        self.reason, self.retry_after = reason, retry_after


# Sliding rate window and both concurrency limits are checked in one transaction.
ACQUIRE = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local window = tonumber(ARGV[2])
local lease = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[2], '-inf', now)
redis.call('ZREMRANGEBYSCORE', KEYS[3], '-inf', now - window)
if redis.call('ZCARD', KEYS[3]) >= tonumber(ARGV[4]) then return 1 end
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[5]) then return 2 end
if redis.call('ZCARD', KEYS[2]) >= tonumber(ARGV[6]) then return 2 end
redis.call('ZADD', KEYS[1], now + lease, ARGV[1])
redis.call('ZADD', KEYS[2], now + lease, ARGV[1])
redis.call('ZADD', KEYS[3], now, ARGV[1])
redis.call('EXPIRE', KEYS[1], math.ceil(lease + 1))
redis.call('EXPIRE', KEYS[2], math.ceil(lease + 1))
redis.call('EXPIRE', KEYS[3], math.ceil(window + 1))
return 0
"""
RELEASE = """
redis.call('ZREM', KEYS[1], ARGV[1])
redis.call('ZREM', KEYS[2], ARGV[1])
return 1
"""


@lru_cache(maxsize=4)
def redis_client(url):
    from redis import Redis

    return Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)


def _keys(scope, identity):
    identity = hashlib.sha256(identity.encode()).hexdigest()
    prefix = f"treasure:{{planner}}:{scope}"
    return [
        f"{prefix}:active",
        f"{prefix}:user:{identity}:active",
        f"{prefix}:user:{identity}:rate",
    ]


class LocalLimiter:
    """Thread-safe single-process limiter. Explicitly not a multi-worker guarantee."""

    def __init__(self):
        self.lock = threading.Lock()
        self.active = defaultdict(dict)
        self.rate = defaultdict(deque)

    def acquire(self, keys, token, window, lease, rate, global_limit, user_limit):
        now = time.monotonic()
        with self.lock:
            for key in keys[:2]:
                self.active[key] = {t: end for t, end in self.active[key].items() if end > now}
            hits = self.rate[keys[2]]
            while hits and hits[0] <= now - window:
                hits.popleft()
            if len(hits) >= rate:
                raise Rejected("rate_limit", window)
            if len(self.active[keys[0]]) >= global_limit or len(self.active[keys[1]]) >= user_limit:
                raise Rejected("busy", 5)
            hits.append(now)
            for key in keys[:2]:
                self.active[key][token] = now + lease

    def release(self, keys, token):
        with self.lock:
            for key in keys[:2]:
                self.active[key].pop(token, None)


local_limiter = LocalLimiter()


def paid_mode():
    return settings.AGENT_BACKEND == "claude" or settings.MAPS_MODE == "google"


def _identity(request, scope):
    if scope != "login" and request.user.is_authenticated:
        return f"user:{request.user.pk}"
    # Never trust arbitrary X-Forwarded-For headers. Edge proxy may enforce its own IP limit.
    return "ip:" + request.META.get("REMOTE_ADDR", "unknown")


def bounded_endpoint(scope, paid_access=False):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if paid_access and paid_mode():
                if not request.user.is_authenticated:
                    return JsonResponse({"error": "authentication_required"}, status=401)
                if not request.user.is_active or not request.user.is_staff:
                    return JsonResponse({"error": "paid_access_requires_staff"}, status=403)
            if not settings.PLANNER_LIMITS_ENABLED:
                return view(request, *args, **kwargs)
            keys = _keys(scope, _identity(request, scope))
            token = uuid.uuid4().hex
            rate = settings.PLANNER_LOGIN_RATE if scope == "login" else settings.PLANNER_RATE
            client = None
            try:
                if settings.REDIS_URL:
                    client = redis_client(settings.REDIS_URL)
                    code = client.eval(
                        ACQUIRE,
                        3,
                        *keys,
                        token,
                        60,
                        settings.PLANNER_LEASE_SECONDS,
                        rate,
                        settings.PLANNER_MAX_CONCURRENT,
                        1,
                    )
                    if code:
                        raise Rejected(
                            "rate_limit" if code == 1 else "busy", 60 if code == 1 else 5
                        )
                else:
                    local_limiter.acquire(
                        keys,
                        token,
                        60,
                        settings.PLANNER_LEASE_SECONDS,
                        rate,
                        settings.PLANNER_MAX_CONCURRENT,
                        1,
                    )
            except Rejected as exc:
                response = JsonResponse({"error": exc.reason}, status=429)
                response["Retry-After"] = str(exc.retry_after)
                return response
            except Exception:
                # A failed shared limiter must not grant unlimited paid access.
                return JsonResponse({"error": "admission_control_unavailable"}, status=503)
            try:
                return view(request, *args, **kwargs)
            finally:
                try:
                    if client:
                        client.eval(RELEASE, 2, *keys[:2], token)
                    else:
                        local_limiter.release(keys, token)
                except Exception:
                    pass  # Fail closed: Redis lease expires instead of freeing another request.

        return wrapped

    return decorator


class AdminLoginLimitMiddleware:
    """Cover Django admin's separate login form with the same shared login limiter."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path.rstrip("/") == "/admin/login":
            return bounded_endpoint("login")(self.get_response)(request)
        return self.get_response(request)
