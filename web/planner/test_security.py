"""Authentication, request limits, session behavior, and provider retention regressions."""

import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase, override_settings

from planner import limits
from planner.models import TripLog


@override_settings(AGENT_BACKEND="claude", MAPS_MODE="offline", PLANNER_LIMITS_ENABLED=False)
class PaidAuthTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            "owner", password="test-only-long-password", is_staff=True
        )
        self.member = get_user_model().objects.create_user("member", password="test-only-password")

    @patch("planner.views.get_agent")
    def test_anonymous_paid_request_never_initializes_provider(self, provider):
        response = self.client.post(
            "/api/chat", json.dumps({"message": "hello"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 401)
        provider.assert_not_called()

    @patch("planner.views.get_agent")
    def test_non_staff_cannot_consume_paid_quota(self, provider):
        self.client.force_login(self.member)
        response = self.client.post(
            "/api/chat", json.dumps({"message": "hello"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 403)
        provider.assert_not_called()

    def test_session_login_logout_csrf_contract(self):
        client = Client(enforce_csrf_checks=True)
        state = client.get("/api/session").json()
        self.assertFalse(state["authenticated"])
        payload = json.dumps({"username": "owner", "password": "test-only-long-password"})
        self.assertEqual(
            client.post("/api/login", payload, content_type="application/json").status_code, 403
        )
        response = client.post(
            "/api/login",
            payload,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=state["csrf_token"],
        )
        self.assertEqual(response.status_code, 200)
        state = response.json()
        self.assertTrue(state["paid_access"])
        self.assertEqual(
            client.post(
                "/api/chat", json.dumps({"message": "x"}), content_type="application/json"
            ).status_code,
            403,
        )
        state = client.post(
            "/api/logout",
            "{}",
            content_type="application/json",
            HTTP_X_CSRFTOKEN=state["csrf_token"],
        ).json()
        self.assertFalse(state["authenticated"])

    def test_reset_preserves_authentication(self):
        self.client.force_login(self.staff)
        self.client.post("/api/reset")
        self.assertTrue(self.client.get("/api/session").json()["authenticated"])

    @override_settings(MAPS_MODE="google")
    @patch("planner.views.get_agent")
    def test_google_content_not_saved_in_database_or_session(self, provider):
        self.client.force_login(self.staff)
        provider.return_value.index.search.return_value = []
        provider.return_value.run.return_value = {
            "itinerary": None,
            "reply": "Google-derived-hours-content",
            "preferences": {"note": "provider-content"},
            "tool_calls": [],
        }
        response = self.client.post(
            "/api/chat", json.dumps({"message": "hello"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["history_persisted"])
        self.assertNotIn("history", self.client.session)
        self.assertNotIn("preferences", self.client.session)
        self.assertEqual(TripLog.objects.count(), 0)


@override_settings(
    AGENT_BACKEND="offline",
    MAPS_MODE="offline",
    PLANNER_LIMITS_ENABLED=True,
    REDIS_URL="",
    PLANNER_RATE=2,
    PLANNER_MAX_CONCURRENT=1,
)
class LocalAdmissionTests(TestCase):
    def setUp(self):
        self.patch = patch.object(limits, "local_limiter", limits.LocalLimiter())
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def post(self):
        return self.client.post(
            "/api/chat", json.dumps({"message": ""}), content_type="application/json"
        )

    def test_rate_limited_even_for_repeated_invalid_requests(self):
        self.assertEqual(self.post().status_code, 400)
        self.assertEqual(self.post().status_code, 400)
        response = self.post()
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response["Retry-After"], "60")

    def test_concurrent_admission_and_release(self):
        keys = limits._keys("chat", "ip:127.0.0.1")
        limits.local_limiter.acquire(keys, "first", 60, 180, 10, 1, 1)
        self.assertEqual(self.post().status_code, 429)
        limits.local_limiter.release(keys, "first")
        self.assertEqual(self.post().status_code, 400)

    @override_settings(REDIS_URL="redis://unavailable:6379/0")
    @patch("planner.limits.redis_client", side_effect=RuntimeError("unavailable"))
    def test_limiter_failure_is_fail_closed(self, client):
        self.assertEqual(self.post().status_code, 503)

    def test_liveness_works_without_artifacts_or_provider(self):
        with patch("planner.views.get_agent", side_effect=RuntimeError("not loaded")):
            self.assertEqual(self.client.get("/healthz").status_code, 200)

    @patch("planner.views.cache.set", side_effect=RuntimeError("cache failed"))
    def test_readiness_fails_if_cache_fails(self, mocked):
        self.assertEqual(self.client.get("/readyz").status_code, 503)


class RedisAtomicScriptTests(SimpleTestCase):
    """Runs actual Lua via fakeredis[lua]; no live external service required."""

    def setUp(self):
        try:
            import fakeredis
            import lupa  # noqa: F401
        except ImportError:
            self.skipTest("Install fakeredis[lua] to exercise Redis Lua scripts")
        self.redis = fakeredis.FakeRedis(decode_responses=True)

    def acquire(self, identity, token, rate=2, global_limit=2):
        keys = limits._keys("chat", identity)
        return self.redis.eval(limits.ACQUIRE, 3, *keys, token, 60, 180, rate, global_limit, 1)

    def release(self, identity, token):
        keys = limits._keys("chat", identity)
        self.redis.eval(limits.RELEASE, 2, *keys[:2], token)

    def test_lua_user_and_global_concurrency_and_rate(self):
        self.assertEqual(self.acquire("a", "first"), 0)
        self.assertEqual(self.acquire("a", "second"), 2)
        self.assertEqual(self.acquire("b", "third"), 0)
        self.assertEqual(self.acquire("c", "fourth"), 2)
        self.release("a", "first")
        self.assertEqual(self.acquire("a", "fifth"), 0)
        self.release("a", "fifth")
        self.assertEqual(self.acquire("a", "sixth"), 1)

    def test_old_release_does_not_free_new_lease(self):
        self.assertEqual(self.acquire("a", "old"), 0)
        for key in limits._keys("chat", "a")[:2]:
            self.redis.zadd(key, {"old": 0})
        self.assertEqual(self.acquire("a", "new"), 0)
        self.release("a", "old")
        self.assertEqual(self.acquire("a", "extra", rate=10), 2)


class RetentionTests(TestCase):
    def test_retention_command_defaults_to_dry_run(self):
        from datetime import timedelta
        from io import StringIO
        from django.core.management import call_command
        from django.utils import timezone

        old = TripLog.objects.create(session_key="old", user_text="old", reply="old")
        TripLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=40))
        TripLog.objects.create(session_key="new", user_text="new", reply="new")
        call_command("purge_planner_logs", stdout=StringIO())
        self.assertEqual(TripLog.objects.count(), 2)
        call_command("purge_planner_logs", "--apply", stdout=StringIO())
        self.assertEqual(TripLog.objects.count(), 1)
        self.assertEqual(TripLog.objects.get().session_key, "new")
