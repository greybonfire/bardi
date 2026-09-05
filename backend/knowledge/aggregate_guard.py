"""Guard aggregate-owned catalog relationships from ad-hoc ORM mutation.

Question resolved-Fact sets and contradiction Fact declarations have invariants that
span multiple rows. They are therefore mutated through the transactional services in
``knowledge.services`` rather than by saving/deleting individual through rows.

Django bulk/update operations intentionally bypass model signals. Production code must
not use those operations for these relations outside the catalog services; this module
protects the ordinary ORM and Admin paths where accidental partial writes are most likely.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from django.core.exceptions import ValidationError
from django.db.models import Model, QuerySet
from django.db.models.signals import pre_delete, pre_save

_ALLOW_AGGREGATE_MUTATION: ContextVar[bool] = ContextVar(
    "knowledge_allow_aggregate_mutation", default=False
)


@contextmanager
def allow_aggregate_relation_mutation() -> Iterator[None]:
    """Permit one trusted aggregate mutation performed by a catalog service."""

    token = _ALLOW_AGGREGATE_MUTATION.set(True)
    try:
        yield
    finally:
        _ALLOW_AGGREGATE_MUTATION.reset(token)


def _mutation_error(sender: type[Model]) -> ValidationError:
    if sender.__name__ == "ServiceQuestionResolvedFact":
        service = "set_question_resolved_facts()"
    elif sender.__name__ == "EvidenceLinkSource":
        service = "set_evidence_link_sources()"
    else:
        service = "set_contradiction_facts()"
    return ValidationError(f"Aggregate relation rows must be changed through {service}.")


def _guard_save(sender: type[Model], **kwargs: Any) -> None:
    if not _ALLOW_AGGREGATE_MUTATION.get():
        raise _mutation_error(sender)


def _guard_delete(sender: type[Model], origin: object, **kwargs: Any) -> None:
    if _ALLOW_AGGREGATE_MUTATION.get():
        return

    # Cascades caused by deleting the owning Question/Contradiction are legitimate.
    # Block only deletion initiated directly on the through model/its queryset.
    if isinstance(origin, sender):
        raise _mutation_error(sender)
    if isinstance(origin, QuerySet) and origin.model is sender:
        raise _mutation_error(sender)


def connect_aggregate_relation_guards() -> None:
    """Connect guards once Django's app registry is ready."""

    from .models import EvidenceLinkSource, ServiceContradictionFact, ServiceQuestionResolvedFact

    for model in (ServiceQuestionResolvedFact, ServiceContradictionFact, EvidenceLinkSource):
        pre_save.connect(
            _guard_save,
            sender=model,
            weak=False,
            dispatch_uid=f"knowledge.guard_save.{model.__name__}",
        )
        pre_delete.connect(
            _guard_delete,
            sender=model,
            weak=False,
            dispatch_uid=f"knowledge.guard_delete.{model.__name__}",
        )
