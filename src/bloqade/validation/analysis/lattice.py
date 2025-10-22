from typing import final
from dataclasses import dataclass

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
    """Indicates an error in the IR."""

    message: str = ""
    """Optional error message to show in the IR.

    NOTE: this is just to show a message when printing the IR. Actual errors
    are collected by appending ir.ValidationError to the frame in the method
    implementation.
    """


@final
@dataclass
class NoError(ErrorType, metaclass=SingletonMeta):
    pass
