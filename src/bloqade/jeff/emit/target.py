"""This module holds the entry point that emits a jeff program as a jeff module."""

from importlib.metadata import version

from kirin import ir, types
from kirin.dialects import func

from jeff import JeffFunc, JeffModule
from bloqade.jeff.types import is_subtype
from bloqade.jeff.dialects import stmts, kernel as jeff_kernel
from bloqade.jeff.emit.base import EmitJeff


def _argument(
    value: object, declared: types.TypeAttribute
) -> stmts.ConstInt | stmts.ConstFloat | None:
    """Return the jeff constant for an argument.

    The function returns None if the argument does not fit the declared parameter type.
    """
    if isinstance(value, bool) and is_subtype(declared, types.Bool):
        return stmts.ConstInt(value=int(value), bitwidth=1)
    if (
        isinstance(value, int)
        and not isinstance(value, bool)
        and is_subtype(declared, types.Int)
        and not is_subtype(declared, types.Bool)
    ):
        return stmts.ConstInt(value=value)
    if isinstance(value, float) and is_subtype(declared, types.Float):
        return stmts.ConstFloat(value=value)
    return None


class _Module(JeffModule):
    """Hold a jeff module that writes its string table in sorted order."""

    def _compute_strings(self) -> list[str]:
        """Return the strings of the module in sorted order."""
        return sorted(super()._compute_strings())


def emit_jeff(method: ir.Method, args: tuple[object, ...] = ()) -> JeffModule:
    """Emit a jeff program as a jeff module.

    Each constant in `args` replaces the matching leading parameter of the program.
    """
    if not isinstance(method, ir.Method) or method.dialects is not jeff_kernel:
        raise TypeError(
            "emit_jeff takes a jeff program in the `jeff.kernel` dialect group. "
            "Lower a squin kernel with SquinToJeff first."
        )
    if not isinstance(args, tuple):
        raise TypeError(
            f"args must be a tuple of constants, but it is a {type(args).__name__}."
        )
    callable_region = method.callable_region
    if callable_region.blocks[0].first_stmt is None:
        raise TypeError("The program's body is empty.")
    if not args:
        return _module(method.code)

    sym_name = (
        method.code.get_present_trait(ir.SymbolOpInterface)
        .get_sym_name(method.code)
        .data
    )
    params = method.self_type.params_type
    constants: list[stmts.ConstInt | stmts.ConstFloat] = []
    for position, (value, declared) in enumerate(zip(args, params)):
        constant = _argument(value, declared)
        if constant is None:
            raise TypeError(
                f"args[{position}] is {value!r} where the program's parameter is "
                f"{declared}."
            )
        constants.append(constant)

    callable_region = callable_region.clone()
    entry_block = callable_region.blocks[0]
    block_args = list(entry_block.args)
    first_stmt = entry_block.first_stmt
    assert first_stmt is not None
    if len(args) > len(block_args) - 1:
        raise ValueError("There are more args than kernel parameters.")
    for const, arg_ssa in zip(constants, block_args[1:]):
        const.insert_before(first_stmt)
        arg_ssa.replace_by(const.result)
        entry_block.args.delete(arg_ssa)

    return _module(
        func.Function(
            sym_name=sym_name,
            body=callable_region,
            signature=func.Signature(
                inputs=tuple(params[len(args) :]), output=method.return_type
            ),
        )
    )


def _module(code: ir.Statement) -> JeffModule:
    """Emit `code` and every function that it calls as one jeff module."""
    emitter = EmitJeff(dialects=jeff_kernel)
    emitter.run(code)
    functions: list[JeffFunc] = list(emitter.function_defs)
    module = _Module(
        functions,
        entrypoint=0,
        tool="bloqade-circuit",
        tool_version=version("bloqade-circuit"),
    )
    module.refresh()
    return module
