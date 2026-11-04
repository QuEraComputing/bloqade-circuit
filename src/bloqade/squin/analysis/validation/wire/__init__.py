"""Check wire structure, types, uses, borrows and positions."""

from .borrows import (
    Slots as Slots,
    KnownSlots as KnownSlots,
    BorrowCheck as BorrowCheck,
    UnknownSlots as UnknownSlots,
    BorrowValidation as BorrowValidation,
    UnreachableSlots as UnreachableSlots,
)
from .position import PositionValidation as PositionValidation
from .linearity import LinearityValidation as LinearityValidation
from .validation import (
    WireValidation as WireValidation,
    StructureValidation as StructureValidation,
)
