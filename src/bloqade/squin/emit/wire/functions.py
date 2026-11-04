"""Emit function boundaries, library wrappers and calls in the wire convention."""

from typing import cast
from dataclasses import replace

from kirin import ir, types, interp
from kirin.dialects import py, func

from bloqade import qubit
from bloqade.types import is_subtype
from bloqade.squin.wire import stmts
from bloqade.analysis.indices import IndexExpr
from bloqade.squin.wire.group import wire_group
from bloqade.squin.wire.types import (
    WireType,
    quantum_type,
    parameter_type,
    register_shape,
)
from bloqade.squin.wire.errors import (
    WireConversionError,
)
from bloqade.squin.wire.signature import (
    Layout,
    packed_type,
    output_types,
)

from .base import EmitWire, WireFrame, body_of
from .values import (
    Grid,
    Qubit,
    Value,
    Element,
    Register,
    is_qubit,
    contains_location,
)

LIBRARIES = ("bloqade.squin.stdlib", "bloqade.qubit.stdlib", "bloqade.native.stdlib")
"""The modules whose kernels wrap source quantum operations for users."""


def is_library(method: ir.Method) -> bool:
    """Check whether `method` is a kernel of a module in `LIBRARIES`.

    The emitter runs the body of a library kernel at each call. It keeps an explicit
    call for every other kernel.
    """
    module = method.mod.__name__ if method.mod is not None else ""
    return module.startswith(LIBRARIES)


@func.dialect.register(key="emit.squin_wire")
class Functions(interp.MethodTable):
    """Emit function boundaries and calls in the calling convention of `Layout`."""

    @interp.impl(func.Function)
    def function(
        self, emit: EmitWire, frame: WireFrame, stmt: func.Function
    ) -> tuple[()]:
        """Emit the wire form of the source function and record the wire method.

        Every ordinary result must be classical. A function can allocate and free
        qubits, but it returns qubits only through its borrowed parameters.
        """
        if isinstance(stmt.signature.output, types.BottomType):
            raise WireConversionError(
                "The function return has the impossible type Bottom.", stmt
            )
        layout = Layout.of(stmt.signature)
        block = body_of(stmt.body, stmt, len(stmt.signature.inputs) + 1)
        input_types = tuple(parameter_type(kind) for kind in stmt.signature.inputs)
        # The emitted body decides the output type, so the self argument gets its
        # final type after the body.
        self_arg = frame.output.args.append_from(types.Any, block.args[0].name)
        parameter_values = [
            add_parameter(frame, source, kind)
            for source, kind in zip(block.args[1:], input_types, strict=True)
        ]
        returned = emit.frame_call(frame, stmt, self_arg, *parameter_values)
        end = block.last_stmt
        assert isinstance(end, func.Return)

        ordinary = ordinary_values(emit, frame, stmt, end, layout, returned)
        if any(contains_location(value) for value in ordinary):
            raise WireConversionError(
                "A function cannot return qubits. Allocate them in the caller and"
                " pass them in.",
                end,
            )
        borrowed = [
            cast(Qubit | Register | Grid, parameter_values[i])
            for i in layout.borrowed_positions
        ]
        results = (
            *(emit.classical_value(frame, value) for value in ordinary),
            *(emit.acquire(frame, location) for location in borrowed),
        )
        frame.free_local_allocations()
        emit_return(frame, results)

        signature = func.Signature(
            input_types, packed_type(tuple(value.type for value in results))
        )
        self_arg.type = types.MethodType[list(input_types), signature.output]
        method = wire_method(
            emit.source, stmt, frame.output, signature, emit.wire_dialects
        )
        emit.result = method
        return ()

    @interp.impl(func.Return)
    def return_(
        self, emit: EmitWire, frame: WireFrame, stmt: func.Return
    ) -> interp.ReturnValue[Value]:
        """Return the source value to the function or library call that runs the body."""
        # A loop or branch frame has the loop or the branch as its code.
        if (
            not isinstance(frame.code, func.Function)
            or stmt.parent_stmt is not frame.code
        ):
            raise WireConversionError(
                "Wire conversion requires a function-level return.", stmt
            )
        return interp.ReturnValue(frame.get(stmt.value))

    @interp.impl(func.Call)
    def call(self, emit: EmitWire, frame: WireFrame, stmt: func.Call) -> tuple[()]:
        """Reject a call through a function value, which names no static callee."""
        raise WireConversionError("Wire emission requires a static call target.", stmt)

    @interp.impl(func.Invoke)
    def invoke(
        self, emit: EmitWire, frame: WireFrame, stmt: func.Invoke
    ) -> tuple[Value]:
        """Allocate a register, run a library wrapper or call a converted function."""
        if stmt.callee is qubit.qalloc:
            return (allocate_register(emit, frame, stmt),)
        if is_library(stmt.callee):
            return (run_library(emit, frame, stmt),)
        return (call(emit, frame, stmt),)


def add_parameter(
    frame: WireFrame, source: ir.BlockArgument, kind: types.TypeAttribute
) -> Value:
    """Add the wire parameter of a source parameter and return the source meaning.

    A quantum parameter becomes a whole `Qubit` or `Register`. A register knows its
    dimensions if the source type gives them.
    """
    argument = frame.output.args.append_from(kind, source.name)
    if quantum_type(source.type) is None:
        return argument
    frame.latest[argument] = argument
    if kind == WireType:
        return Qubit(argument)
    shape = register_shape(source.type)
    outer = shape[0] if shape else None
    length = None if outer is None else IndexExpr(outer)
    if len(shape) > 1:
        return Grid(argument, length, shape[1:])
    return Register(argument, length)


def ordinary_values(
    emit: EmitWire,
    frame: WireFrame,
    function: func.Function,
    end: func.Return,
    layout: Layout,
    value: Value,
) -> tuple[Value, ...]:
    """Split the returned source value into the ordinary results of `layout`."""
    if not layout.ordinary_count:
        return ()
    if not layout.packed:
        return (value,)
    if not isinstance(value, tuple):
        kinds = output_types(function.signature.output)
        return unpack(frame, emit.classical_value(frame, value), kinds)
    if len(value) != layout.ordinary_count:
        raise WireConversionError(
            "The returned tuple must match the declared result count.", end
        )
    return value


def emit_return(frame: WireFrame, results: tuple[ir.SSAValue, ...]) -> None:
    """Emit a `Return` of `None`, of the single result or of a tuple of the results."""
    if not results:
        packed = frame.push(func.ConstantNone()).results[0]
    elif len(results) == 1:
        packed = results[0]
    else:
        packed = frame.push(py.tuple.New(results)).results[0]
    frame.push(func.Return(packed))


def wire_method(
    source: ir.Method,
    stmt: func.Function,
    body: ir.Block,
    signature: func.Signature,
    wire_dialects: tuple[ir.Dialect, ...] = (),
) -> ir.Method:
    """Build the wire method with the body `body` and the metadata of `source`.

    `wire_dialects` joins the dialect group, so the method can hold wire statements
    of other dialects.
    """
    code = stmt.from_stmt(stmt, regions=[ir.Region(body)])
    code.source = None if stmt.source is None else replace(stmt.source)
    code.signature = signature
    return ir.Method(
        wire_group(source.dialects, wire_dialects),
        code,
        nargs=source.nargs,
        mod=source.mod,
        py_func=source.py_func,
        sym_name=source.sym_name,
        arg_names=source.arg_names,
        fields=source.fields,
        file=source.file,
        lineno_begin=source.lineno_begin,
    )


def allocate_register(emit: EmitWire, frame: WireFrame, stmt: func.Invoke) -> Register:
    """Emit the register of a `qalloc` call and return its location.

    The library body of `qalloc` builds the register with a list map, which the
    emitter cannot run. This function emits one `AllocRegister` in its place.
    """
    size = emit.classical_value(frame, frame.get(stmt.inputs[0]))
    root = frame.push(stmts.AllocRegister(size)).results[0]
    frame.latest[root] = root
    frame.local_roots.append(root)
    length = emit.index(stmt.inputs[0])
    # A negative constant size gives an empty register, like `range(n)`.
    if (count := length.constant) is not None:
        length = IndexExpr(max(0, count))
    return Register(root, length)


def run_library(emit: EmitWire, frame: WireFrame, stmt: func.Invoke) -> Value:
    """Emit the body of a library wrapper in place of its call and return its result.

    The wrapper emits into the caller's block and continues the caller's wires.
    Its allocations live until the caller's region ends.
    """
    # The body reads the caller's integers when it emits an index of a caller
    # location, so the frame has parent access.
    with emit.new_frame(stmt.callee.code, has_parent_access=True) as body:
        body.site = frame.site or stmt
        body.output = frame.output
        body.latest = frame.latest
        body.local_roots = frame.local_roots
        # A wrapper body never uses its self argument, which has no emitted form.
        result = emit.frame_call(
            body, stmt.callee.code, None, *frame.get_values(stmt.inputs)
        )
    return result


def call(emit: EmitWire, frame: WireFrame, stmt: func.Invoke) -> Value:
    """Call a converted function and continue the borrowed qubits with its results."""
    if any(is_subtype(value.type, types.Tuple) for value in stmt.inputs):
        raise WireConversionError(
            "Wire calls require separate arguments for tuple fields.", stmt
        )
    callee = stmt.callee.code
    assert isinstance(callee, func.Function)
    layout = Layout.of(callee.signature)
    wired = emit.converted[stmt.callee]
    arguments = frame.get_values(stmt.inputs)
    borrowed = borrowed_operands(arguments, layout, stmt)
    check_shapes(callee, layout, borrowed, stmt)
    location_at = dict(zip(layout.borrowed_positions, borrowed, strict=True))
    inputs = tuple(
        (
            emit.acquire(frame, location_at[i])
            if i in location_at
            else emit.classical_value(frame, argument)
        )
        for i, argument in enumerate(arguments)
    )
    made = frame.push(func.Invoke(inputs, callee=wired))
    made.result.type = wired.return_type
    outputs = call_results(frame, made.result, layout)
    count = layout.ordinary_count
    for location, result in zip(borrowed, outputs[count:], strict=True):
        emit.restore(frame, location, result)
    ordinary = outputs[:count]
    if layout.packed:
        return ordinary
    return ordinary[0] if ordinary else frame.push(func.ConstantNone()).results[0]


def borrowed_operands(
    arguments: tuple[Value, ...], layout: Layout, stmt: func.Invoke
) -> list[Qubit | Register | Grid | Element]:
    """Return the borrowed call operands, which must be qubits or whole registers.

    The borrow check rejects 2 operands that provably name the same qubit.
    """
    operands = [arguments[i] for i in layout.borrowed_positions]
    if not all(isinstance(x, (Qubit, Register, Grid, Element)) for x in operands):
        raise WireConversionError(
            "A call requires whole registers or individual qubits.", stmt
        )
    return cast(list[Qubit | Register | Grid | Element], operands)


def check_shapes(
    callee: func.Function,
    layout: Layout,
    borrowed: list[Qubit | Register | Grid | Element],
    stmt: func.Invoke,
) -> None:
    """Require each quantum argument to have the shape that its parameter declares.

    The callee reads register dimensions from its parameter types, so an argument
    of another shape would make it address the wrong qubits.
    """
    parameters = callee.body.blocks[0].args[1:]
    for position, operand in zip(layout.borrowed_positions, borrowed, strict=True):
        kind = parameters[position].type
        if quantum_type(kind) == WireType:
            if not is_qubit(operand):
                raise WireConversionError(
                    "A qubit parameter requires one qubit argument.", stmt
                )
            continue
        if not isinstance(operand, (Register, Grid)):
            raise WireConversionError(
                "A register parameter requires a whole register argument.", stmt
            )
        expected = register_shape(kind)
        actual = shape_of(operand)
        if len(expected) != len(actual) or any(
            size is not None and size != given for size, given in zip(expected, actual)
        ):
            raise WireConversionError(
                "A register argument must provably have the shape that its"
                " parameter declares.",
                stmt,
            )


def shape_of(register: Register | Grid) -> tuple[int | None, ...]:
    """Return the known dimensions of a whole register, outermost first."""
    outer = None if register.length is None else register.length.constant
    if isinstance(register, Grid):
        return (outer, *register.row_shape)
    return (outer,)


def call_results(
    frame: WireFrame, result: ir.SSAValue, layout: Layout
) -> tuple[ir.SSAValue, ...]:
    """Split the result of a wire call into one value for each wire result."""
    kinds = layout.result_types(result.type)
    if not kinds:
        return ()
    if len(kinds) == 1:
        return (result,)
    return unpack(frame, result, kinds)


def unpack(
    frame: WireFrame, packed: ir.SSAValue, kinds: tuple[types.TypeAttribute, ...]
) -> tuple[ir.SSAValue, ...]:
    """Read each field of the tuple value `packed` and give it the type in `kinds`."""
    fields: list[ir.SSAValue] = []
    for i, kind in enumerate(kinds):
        index = frame.push(py.Constant(i)).results[0]
        item = frame.push(py.GetItem(packed, index))
        item.results[0].type = kind
        fields.append(item.results[0])
    return tuple(fields)
