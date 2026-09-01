"""ASGI config for the Bardi project."""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bardi.settings.production")

application = get_asgi_application()
