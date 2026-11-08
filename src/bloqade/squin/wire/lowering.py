"""Compile Python kernels directly to validated wire operations."""

from types import FunctionType
from typing import TypeVar, ParamSpec, cast
from collections.abc import Callable

from kirin import ir

from ._lowering import Compiler

Param = ParamSpec("Param")
Return = TypeVar("Return")


def wire_kernel(function: Callable[Param, Return]) -> ir.Method[Param, Return]:
    """Lower Python syntax with explicit wire ownership and validate the result."""
    return Compiler().compile(cast(FunctionType, function))
