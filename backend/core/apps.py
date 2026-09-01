from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Application configuration for the production scaffold."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
