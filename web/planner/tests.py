"""Website tests. They use the fake planner, so no API key or money is needed.

    cd web && python manage.py test planner
(needs data/processed and artifacts/ - run the pipeline on FAKE data first)
"""

import json
from unittest.mock import patch

from django.test import TestCase, override_settings

from planner import views
from planner.models import PlaceFeedback, TripLog


@override_settings(AGENT_BACKEND="fake", PLANNER_LIMITS_ENABLED=False)
class ChatTests(TestCase):
    def setUp(self):
        views.get_agent.cache_clear()

    def test_home_page_loads(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, "Treasure Travel")

    def test_chat_returns_a_plan_and_logs_it(self):
        r = self.client.post(
            "/api/chat",
            json.dumps({"message": "2 people on Saturday from 10:00, art and coffee"}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIn("reply", data)
        self.assertEqual(TripLog.objects.count(), 1)
        # the conversation is remembered for the next turn
        self.assertEqual(len(self.client.session["history"]), 2)

    def test_feedback_is_saved(self):
        r = self.client.post(
            "/api/feedback",
            json.dumps({"place_id": "x", "place_name": "Y", "liked": True}),
            content_type="application/json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(PlaceFeedback.objects.filter(liked=True).count(), 1)

    def test_bad_request(self):
        r = self.client.post("/api/chat", "not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)


@override_settings(PLANNER_LIMITS_ENABLED=False)
class InputValidationTests(TestCase):
    def test_chat_rejects_non_object_or_non_string_message(self):
        for value in [
            None,
            [],
            1,
            "text",
            {},
            {"message": None},
            {"message": []},
            {"message": " "},
            {"message": "x" * 8001},
        ]:
            with self.subTest(value=type(value).__name__):
                response = self.client.post(
                    "/api/chat", json.dumps(value), content_type="application/json"
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(TripLog.objects.count(), 0)

    def test_feedback_rejects_coerced_booleans_and_bad_fields(self):
        values = [
            None,
            [],
            "text",
            {},
            {"place_id": "a", "liked": "false"},
            {"place_id": "a", "liked": 0},
            {"place_id": "", "liked": True},
            {"place_id": "a" * 129, "liked": True},
            {"place_id": "a", "liked": True, "place_name": []},
        ]
        for value in values:
            response = self.client.post(
                "/api/feedback", json.dumps(value), content_type="application/json"
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(PlaceFeedback.objects.count(), 0)

    def test_false_feedback_is_preserved(self):
        self.client.post(
            "/api/feedback",
            json.dumps({"place_id": "a", "liked": False}),
            content_type="application/json",
        )
        self.assertFalse(PlaceFeedback.objects.get().liked)

    @patch("planner.views.get_agent", side_effect=RuntimeError("secret-token"))
    def test_provider_failure_has_safe_response_and_no_partial_log(self, mocked):
        response = self.client.post(
            "/api/chat", json.dumps({"message": "coffee"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "secret-token", status_code=503)
        self.assertEqual(TripLog.objects.count(), 0)

    @patch("planner.views.get_agent")
    def test_preferences_reach_agent_and_reset_clears_session(self, mocked):
        session = self.client.session
        session["preferences"] = {"budget": 0, "day": "Monday"}
        session.save()
        agent = mocked.return_value
        agent.index.search.return_value = []
        agent.run.return_value = {
            "itinerary": None,
            "reply": "What time?",
            "preferences": {"budget": 0},
            "tool_calls": [],
        }
        self.client.post(
            "/api/chat", json.dumps({"message": "a free trip"}), content_type="application/json"
        )
        self.assertEqual(agent.run.call_args.kwargs["request"]["budget"], 0)
        self.assertEqual(self.client.session["preferences"], {"budget": 0})
        self.client.post("/api/reset")
        self.assertNotIn("preferences", self.client.session)
        self.assertNotIn("history", self.client.session)

    @patch("planner.views.get_agent")
    def test_itinerary_is_retained_for_follow_up_questions(self, mocked):
        import pandas as pd

        agent = mocked.return_value
        agent.index.search.return_value = []
        agent.index.by_id = {"museum": 0}
        agent.index.places = pd.DataFrame(
            [{"name": "Museum", "categories": "Art museum", "price": ""}]
        )
        plan = {
            "stops": [{"place_id": "museum", "arrive": "10:00", "leave": "11:00"}],
            "summary": "Visit the museum.",
        }
        agent.run.return_value = {
            "itinerary": plan,
            "reply": "Visit the museum.",
            "preferences": {},
            "tool_calls": [],
        }
        response = self.client.post(
            "/api/chat", json.dumps({"message": "art please"}), content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('"place_id": "museum"', self.client.session["history"][-1]["content"])


@override_settings(AGENT_BACKEND="offline", PLANNER_LIMITS_ENABLED=False)
class OfflineWebTests(TestCase):
    def setUp(self):
        views.get_agent.cache_clear()

    def tearDown(self):
        views.get_agent.cache_clear()

    @patch("planner.views.make_maps")
    @patch("planner.views.PlaceIndex")
    def test_offline_backend_asks_missing_fields_without_model_call(self, index, maps):
        with patch("planner.views.ClaudeLLM") as llm:
            response = self.client.post(
                "/api/chat",
                json.dumps({"message": "art and coffee"}),
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["stops"], [])
            self.assertIn("origin", response.json()["reply"])
            llm.assert_not_called()
            index.return_value.search.assert_not_called()

    def test_offline_banner_is_explicit(self):
        response = self.client.get("/")
        self.assertContains(response, "not an LLM")
