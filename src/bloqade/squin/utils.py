from __future__ import annotations

import linecache
from typing import Any
from keyword import iskeyword
from itertools import count

from kirin import ir

from ..qubit import qalloc, broadcast
from .groups import kernel

_wrap_counter = count()


def wrap(
    method: ir.Method,
    /,
    n_qubits: int | None = None,
    **kwargs: Any,
) -> ir.Method:
    """Wrap a qubit kernel in an allocating and measuring entry-point.

    Args:
        method: Kernel to invoke on the allocated qubits.
        n_qubits: Number of qubits to allocate. When omitted, this is inferred
            from the method's unsupplied parameters.
        **kwargs: Kernel keyword arguments to bind in the wrapped entry-point.

    Returns:
        A ``squin.kernel`` method that allocates qubits, invokes ``method``, and
        returns measurements for all allocated qubits.
    """
    if not isinstance(method, ir.Method):
        raise TypeError(f"expected a Kirin Method, got {type(method).__name__}")

    param_names = _method_param_names(method)
    _validate_kwargs(param_names, kwargs)

    if n_qubits is None:
        n_qubits = len(param_names) - len(kwargs)

    if n_qubits < 0:
        raise ValueError("n_qubits must be non-negative")

    _validate_qubit_arguments(param_names, n_qubits, kwargs)

    if len(param_names) != n_qubits + len(kwargs):
        raise ValueError(
            f"cannot call {method.sym_name or 'method'} with {n_qubits} qubits "
            f"and {len(kwargs)} keyword arguments; expected {len(param_names)} "
            "total arguments"
        )

    return _compile_wrapper(method, n_qubits, kwargs)


def _method_param_names(method: ir.Method) -> list[str]:
    if method.arg_names is None:
        return [f"arg{i}" for i in range(method.nargs - 1)]
    return list(method.arg_names[1:])


def _validate_kwargs(param_names: list[str], kwargs: dict[str, Any]) -> None:
    unexpected = set(kwargs).difference(param_names)
    if unexpected:
        unexpected_names = ", ".join(sorted(unexpected))
        raise TypeError(f"unexpected keyword argument(s): {unexpected_names}")

    for name in kwargs:
        if not name.isidentifier() or iskeyword(name):
            raise ValueError(f"invalid keyword argument name: {name!r}")


def _validate_qubit_arguments(
    param_names: list[str],
    n_qubits: int,
    kwargs: dict[str, Any],
) -> None:
    qubit_params = set(param_names[:n_qubits])
    bound_qubits = qubit_params.intersection(kwargs)
    if bound_qubits:
        names = ", ".join(sorted(bound_qubits))
        raise TypeError(
            "qubit arguments are allocated by squin.wrap and cannot be bound "
            f"by keyword: {names}"
        )


def _compile_wrapper(
    wrapped_method: ir.Method,
    n_qubits: int,
    kwargs: dict[str, Any],
) -> ir.Method:
    positional_args = [f"qubits[{idx}]" for idx in range(n_qubits)]
    keyword_globals = {
        f"__wrapped_kwarg_{idx}__": value for idx, value in enumerate(kwargs.values())
    }
    keyword_args = [
        f"{name}={global_name}"
        for name, global_name in zip(kwargs, keyword_globals, strict=True)
    ]
    call_args = ", ".join(positional_args + keyword_args)

    call_line = (
        f"    __wrapped_method__({call_args})"
        if call_args
        else "    __wrapped_method__()"
    )
    source = (
        "def main():\n"
        f"    qubits = __qalloc__({n_qubits})\n"
        f"{call_line}\n"
        "    return __broadcast__.measure(qubits)\n"
    )

    filename = (
        f"<bloqade.squin.wrap:{wrapped_method.sym_name or 'anonymous'}:"
        f"{next(_wrap_counter)}>"
    )
    linecache.cache[filename] = (
        len(source),
        None,
        source.splitlines(keepends=True),
        filename,
    )

    globals_ = {
        "__wrapped_method__": wrapped_method,
        "__qalloc__": qalloc,
        "__broadcast__": broadcast,
        **keyword_globals,
    }
    locals_: dict[str, Any] = {}
    exec(compile(source, filename, "exec"), globals_, locals_)
    return kernel(locals_["main"])
