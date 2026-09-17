"""Private draft authoring interface; transport imports need no Django setup."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .service import export_draft_context, export_draft_pack, import_draft_pack

__all__ = ["import_draft_pack", "export_draft_pack", "export_draft_context"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import service

        return getattr(service, name)
    raise AttributeError(name)
