from django.contrib import admin

from .models import PlaceFeedback, TripLog


@admin.register(TripLog)
class TripLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "session_key", "user_text")
    search_fields = ("user_text", "reply")


@admin.register(PlaceFeedback)
class PlaceFeedbackAdmin(admin.ModelAdmin):
    list_display = ("created_at", "place_name", "liked", "session_key")
    list_filter = ("liked",)
