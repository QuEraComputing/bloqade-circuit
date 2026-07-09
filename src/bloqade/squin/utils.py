from __future__ import annotations

from typing import Any

from kirin import ir, types
from kirin.dialects import py, func, ilist

from bloqade import qubit
from bloqade.types import QubitType, MeasurementResultType


def _is_qubit_type(typ: types.TypeAttribute) -> bool:
    return typ.is_subseteq(QubitType)


def _is_qubit_register_type(typ: types.TypeAttribute) -> bool:
    return typ.is_subseteq(ilist.IListType[QubitType])


def _method_param_names(mt: ir.Method, n_inputs: int) -> list[str]:
    if mt.arg_names is None:
        return [f"arg{i}" for i in range(n_inputs)]

    arg_names = list(mt.arg_names)
    if arg_names and arg_names[0] == "#self#":
        arg_names = arg_names[1:]

    if len(arg_names) < n_inputs:
        arg_names.extend(f"arg{i}" for i in range(len(arg_names), n_inputs))

    return arg_names[:n_inputs]


def _resolve_constant_args(
    mt: ir.Method,
    signature: func.Signature,
    positional: tuple[Any, ...],
    kwargs: dict[str, Any],
) -> dict[int, Any]:
    param_names = _method_param_names(mt, len(signature.inputs))
    positional_iter = iter(positional)
    constant_args: dict[int, Any] = {}
    consumed_kwargs: set[str] = set()

    for index, typ in enumerate(signature.inputs):
        if _is_qubit_register_type(typ):
            raise ValueError(
                "wrap only supports kernels with individual Qubit arguments; "
                f"argument {param_names[index]!r} has type {typ}"
            )

        if _is_qubit_type(typ):
            if param_names[index] in kwargs:
                raise ValueError(
                    f"Cannot bind qubit argument {param_names[index]!r}; "
                    "wrap allocates qubits automatically"
                )
            continue

        if param_names[index] in kwargs:
            value = kwargs[param_names[index]]
            consumed_kwargs.add(param_names[index])
        else:
            try:
                value = next(positional_iter)
            except StopIteration as exc:
                raise ValueError(
                    f"Missing constant value for argument {param_names[index]!r}"
                ) from exc

        constant_args[index] = value

    try:
        extra_arg = next(positional_iter)
    except StopIteration:
        pass
    else:
        raise ValueError(f"Too many positional constants passed to wrap: {extra_arg!r}")

    extra_kwargs = set(kwargs) - consumed_kwargs
    if extra_kwargs:
        extra = ", ".join(sorted(extra_kwargs))
        raise ValueError(f"Unknown constant argument(s) for wrapped method: {extra}")

    return constant_args


def _resolve_qubit_arg_indices(mt: ir.Method, signature: func.Signature) -> list[int]:
    param_names = _method_param_names(mt, len(signature.inputs))
    qubit_arg_indices: list[int] = []

    for index, typ in enumerate(signature.inputs):
        if _is_qubit_register_type(typ):
            raise ValueError(
                "wrap only supports kernels with individual Qubit arguments; "
                f"argument {param_names[index]!r} has type {typ}"
            )
        if _is_qubit_type(typ):
            qubit_arg_indices.append(index)

    if not qubit_arg_indices:
        raise ValueError("Expected the wrapped method to take at least one qubit")

    return qubit_arg_indices


def _append_constant(block: ir.Block, value: Any) -> ir.SSAValue:
    stmt = py.constant.Constant(value)
    block.stmts.append(stmt)
    return stmt.result


def _append_getitem(block: ir.Block, obj: ir.SSAValue, index: int) -> ir.SSAValue:
    index_value = _append_constant(block, index)
    stmt = py.indexing.GetItem(obj, index_value)
    block.stmts.append(stmt)
    return stmt.result


def wrap(mt: ir.Method, *args: Any, **kwargs: Any) -> ir.Method:
    """Wrap a qubit kernel in a no-argument allocate/measure kernel.

    The returned method allocates the qubits required by ``mt``, invokes ``mt``
    with those qubits plus the construction-time constants supplied through
    ``args``/``kwargs``, measures the allocated qubits, and returns the
    measurement results.

    Args:
        mt: The method to wrap.
        *args: Positional constant values for non-qubit arguments, in signature
            order.
        **kwargs: Keyword constant values for non-qubit arguments.

    Returns:
        A no-argument Kirin method returning an ``IList`` of measurement results.
    """
    code = mt.code
    if (trait := code.get_trait(ir.HasSignature)) is None:
        raise ValueError("Expected a method whose code has a signature")

    signature = trait.get_signature(code)
    qubit_arg_indices = _resolve_qubit_arg_indices(mt, signature)
    constant_args = _resolve_constant_args(mt, signature, args, kwargs)

    total_qubits = len(qubit_arg_indices)
    output_type = ilist.IListType[MeasurementResultType, types.Any]
    wrapper_signature = func.Signature(inputs=(), output=output_type)
    self_type = types.FunctionType((), output_type)
    body_block = ir.Block(argtypes=(self_type,))

    n_qubits_value = _append_constant(body_block, total_qubits)
    qalloc_stmt = func.Invoke((n_qubits_value,), callee=qubit.qalloc)
    body_block.stmts.append(qalloc_stmt)
    allocated_qubits = qalloc_stmt.result

    invoke_args: list[ir.SSAValue | None] = [None] * len(signature.inputs)
    for qubit_index, arg_index in enumerate(qubit_arg_indices):
        invoke_args[arg_index] = _append_getitem(
            body_block, allocated_qubits, qubit_index
        )

    for index, value in constant_args.items():
        invoke_args[index] = _append_constant(body_block, value)

    if any(arg is None for arg in invoke_args):
        raise ValueError("Could not construct all arguments for wrapped method")

    body_block.stmts.append(func.Invoke(tuple(invoke_args), callee=mt))  # type: ignore[arg-type]

    measure_stmt = func.Invoke((allocated_qubits,), callee=qubit.broadcast.measure)
    body_block.stmts.append(measure_stmt)
    body_block.stmts.append(func.Return(measure_stmt.result))

    sym_name = f"{mt.sym_name}_wrapped"
    wrapper_code = func.Function(
        sym_name=sym_name,
        signature=wrapper_signature,
        body=ir.Region(body_block),
    )
    wrapped = ir.Method(
        mt.dialects,
        wrapper_code,
        nargs=1,
        mod=mt.mod,
        sym_name=sym_name,
        arg_names=["#self#"],
        file=mt.file,
        lineno_begin=mt.lineno_begin,
    )
    mt.dialects.run_pass(wrapped)
    return wrapped
