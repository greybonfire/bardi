"""URL configuration for the Bardi project."""

from api.api import api
from core.health import liveness, readiness
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("health/live", liveness, name="health-live"),
    path("health/ready", readiness, name="health-ready"),
    path("admin/", admin.site.urls),
    path("v1/", api.urls),
]
