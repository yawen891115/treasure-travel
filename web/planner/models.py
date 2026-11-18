"""What we store: every planning turn (for debugging and analysis) and thumbs-up/down ratings."""

from django.db import models


class TripLog(models.Model):
    session_key = models.CharField(max_length=64, db_index=True)
    user_text = models.TextField()
    reply = models.TextField(blank=True)
    itinerary = models.JSONField(null=True, blank=True)
    tool_calls = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PlaceFeedback(models.Model):
    """In-app ratings: a traveler liked (or disliked) a suggested place."""

    session_key = models.CharField(max_length=64, db_index=True)
    place_id = models.CharField(max_length=128)
    place_name = models.CharField(max_length=256, blank=True)
    liked = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
