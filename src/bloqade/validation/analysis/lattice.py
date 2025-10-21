from typing import final
from dataclasses import dataclass

from kirin import ir
from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    IsSubsetEqMixin,
    SimpleJoinMixin,
    SimpleMeetMixin,
)


@dataclass
class ErrorType(
    SimpleJoinMixin["ErrorType"],
    SimpleMeetMixin["ErrorType"],
    IsSubsetEqMixin["ErrorType"],
    BoundedLattice["ErrorType"],
):

    @classmethod
    def bottom(cls) -> "ErrorType":
        return InvalidErrorType()

    @classmethod
    def top(cls) -> "ErrorType":
        return NoError()


@final
@dataclass
class InvalidErrorType(ErrorType, metaclass=SingletonMeta):
    """Bottom to represent when we encounter an error running the analysis.

    When this is encountered, it means there might be an error, but we were unable to tell.
    """

    pass


@final
@dataclass
class Error(ErrorType):
    """We found an error, here's a hopefully helpful message."""

    stmt: ir.IRNode
    msg: str
    help: str | None = None


@final
@dataclass
class NoError(ErrorType, metaclass=SingletonMeta):
    pass
