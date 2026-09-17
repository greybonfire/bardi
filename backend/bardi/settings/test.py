"""Deterministic settings for PostgreSQL-backed Django tests."""

# ruff: noqa: F403,F405
from .base import *

SECRET_KEY = "django-test-only-deterministic-secret-key"
DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")
DATABASES = {"default": postgres_database()}
TEST_RUNNER = "bardi.testing.FreshDatabaseRunner"

# Existing feature-isolation tests author deliberately skeletal Procedure Versions. Selection,
# scenario, and review publication coverage opt back in explicitly so those tests do not need
# synthetic Questions, acceptance records, or reviews unrelated to the feature they exercise.
# Production remains fail-closed.
SELECTION_QUESTIONS_REQUIRED = False
PLANNING_SCENARIOS_REQUIRED = False
PROCEDURE_VERSION_PUBLICATION_GATES = tuple(
    gate
    for gate in PROCEDURE_VERSION_PUBLICATION_GATES
    if gate != "knowledge.review_workflow.ProcedureVersionReviewPublicationGate"
)
