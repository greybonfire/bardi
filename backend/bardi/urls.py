"""URL configuration for the Bardi project."""

from api.api import api
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("v1/", api.urls),
]
