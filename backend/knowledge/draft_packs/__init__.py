"""Private draft authoring interface; transport imports need no Django setup."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .inspection import DraftPackInspection, InspectionChange, inspect_draft_pack
    from .service import export_draft_context, export_draft_pack, import_draft_pack

__all__ = [
    "import_draft_pack",
    "export_draft_pack",
    "export_draft_context",
    "inspect_draft_pack",
    "DraftPackInspection",
    "InspectionChange",
]


def __getattr__(name: str) -> Any:
    if name in {"inspect_draft_pack", "DraftPackInspection", "InspectionChange"}:
        from . import inspection

        return getattr(inspection, name)
    if name in __all__:
        from . import service

        return getattr(service, name)
    raise AttributeError(name)
