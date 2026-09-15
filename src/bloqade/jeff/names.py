"""This module holds the table of statement classes for jeff scalar operations.

Jeff names a scalar operation by a kind, such as `int`, and a subkind, such as `divS`.
"""

from kirin import ir

from .dialects import stmts


def subkind(statement_name: str, prefix: str) -> str:
    """Convert a statement name to jeff's subkind spelling.

    With the prefix ``int_``, ``int_div_s`` becomes ``divS``.
    """
    head, *rest = statement_name.removeprefix(prefix).split("_")
    return head + "".join(part.title() for part in rest)


def _scalars() -> dict[tuple[str, str], type[ir.Statement]]:
    """Return the statement class for each jeff scalar operation."""
    table: dict[tuple[str, str], type[ir.Statement]] = {}
    for cls in stmts.classical.dialect.stmts:
        name = cls.name
        for kind, prefix in (("int", "int_"), ("float", "float_")):
            if name.startswith(prefix) and not name.startswith(
                (f"{prefix}array", f"{prefix}const")
            ):
                table[(kind, subkind(name, prefix))] = cls
    return table


SCALARS = _scalars()
"""The statement class for each pair of jeff kind and subkind.

The table holds each `int_*` and `float_*` statement except constants and arrays.
"""
