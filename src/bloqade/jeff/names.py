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


SCALARS: dict[tuple[str, str], type[ir.Statement]] = {
    (kind, subkind(cls.name, f"{kind}_")): cls
    for cls in stmts.classical.dialect.stmts
    for kind in ("int", "float")
    if cls.name.startswith(f"{kind}_")
    and not cls.name.startswith((f"{kind}_array", f"{kind}_const"))
}
"""The statement class for each pair of jeff kind and subkind.

The table holds each `int_*` and `float_*` statement except constants and arrays.
"""
