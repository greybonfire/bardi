"""Separate Admin instance: importing this never relabels normal Admin."""

from api.api import api
from core.health import liveness, readiness
from django.contrib import admin
from django.urls import path

sandbox_admin = admin.AdminSite(name="admin")
sandbox_admin.site_header = "LOCAL QUESTIONNAIRE SANDBOX"
sandbox_admin.site_title = "LOCAL QUESTIONNAIRE SANDBOX"
sandbox_admin.index_title = "Copied local data — refresh replaces active sandbox changes"
for model, model_admin in admin.site._registry.items():
    sandbox_admin.register(model, type(model_admin))

urlpatterns = [
    path("health/live", liveness, name="health-live"),
    path("health/ready", readiness, name="health-ready"),
    path("admin/", sandbox_admin.urls),
    path("v1/", api.urls),
]
