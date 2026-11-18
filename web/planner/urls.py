from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/chat", views.api_chat, name="api_chat"),
    path("api/feedback", views.api_feedback, name="api_feedback"),
    path("api/reset", views.api_reset, name="api_reset"),
    path("healthz", views.healthz, name="healthz"),
    path("readyz", views.readyz, name="readyz"),
    path("api/session", views.api_session, name="api_session"),
    path("api/login", views.api_login, name="api_login"),
    path("api/logout", views.api_logout, name="api_logout"),
    path("accounts/login/", views.PlannerLoginView.as_view(), name="login"),
]
