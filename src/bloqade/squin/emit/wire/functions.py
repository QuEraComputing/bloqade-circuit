"""Emit function boundaries, library wrappers and calls in the wire convention."""

from typing import cast
from dataclasses import replace

from kirin import ir, types, interp
from kirin.dialects import py, func

from bloqade import qubit
from bloqade.types import is_subtype, holds_qubits, output_types
from bloqade.squin.wire import stmts
from bloqade.analysis.indices import Slice, IndexExpr
from bloqade.squin.wire.group import wire_group
from bloqade.squin.wire.types import WireType
from bloqade.squin.wire.errors import (
    WireConversionError,
)
from bloqade.squin.rewrite.wire.signature import (
    Layout,
    packed_type,
    quantum_type,
    parameter_type,
    register_shape,
)

from .base import EmitWire, WireFrame, body_of
from .values import (
    View,
    Qubit,
    Value,
    Single,
    Element,
    Register,
    WrapperSelf,
    contains_location,
)

LIBRARIES = ("bloqade.squin.stdlib", "bloqade.qubit.stdlib", "bloqade.native.stdlib")
"""Hold the modules whose kernels wrap source quantum operations for users."""


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
        qubits, but it returns qubits only through its in-out parameters.
        """
        if isinstance(stmt.signature.output, types.BottomType):
            raise WireConversionError(
                "The function return has the impossible type Bottom.", stmt
            )
        layout = Layout.of(stmt.signature)
        block = body_of(stmt.body, stmt, len(stmt.signature.inputs) + 1)
        input_types = tuple(parameter_type(typ) for typ in stmt.signature.inputs)
        # The emitted body decides the output type, so the self argument gets its
        # final type after the body.
        self_arg = frame.output.args.append_from(types.Any, block.args[0].name)
        parameter_values = [
            add_parameter(frame, source, typ)
            for source, typ in zip(block.args[1:], input_types, strict=True)
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
        inout = [
            cast(Qubit | Register, parameter_values[i]) for i in layout.inout_positions
        ]
        results = (
            *(emit.classical_value(frame, value) for value in ordinary),
            *(emit.acquire(frame, location) for location in inout),
        )
        frame.free_local_allocations()
        emit_return(frame, results)

        # Kirin constrains inference with the declared output type. Classical
        # results need an unrestricted type until inference checks every path.
        output_types = (
            *(types.Any for _ in ordinary),
            *(input_types[i] for i in layout.inout_positions),
        )
        signature = func.Signature(input_types, packed_type(output_types))
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
        return (call_converted(emit, frame, stmt),)


def add_parameter(
    frame: WireFrame, source: ir.BlockArgument, typ: types.TypeAttribute
) -> Value:
    """Add the wire parameter of a source parameter and return the source meaning.

    A quantum parameter becomes a whole `Qubit` or `Register`. A register knows its
    dimensions if the source type gives them.
    """
    argument = frame.output.args.append_from(typ, source.name)
    if quantum_type(source.type) is None:
        return argument
    if typ == WireType:
        location: Qubit | Register = Qubit(argument)
    else:
        outer, *inner = register_shape(source.type) or (None,)
        length = None if outer is None else IndexExpr(outer)
        location = Register(argument, length, tuple(inner))
    frame.own(location, local=False)
    return location


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
        outputs = output_types(function.signature.output)
        return unpack(frame, emit.classical_value(frame, value), outputs)
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
    length = emit.index(stmt.inputs[0])
    if (count := length.constant) is not None and count < 0:
        raise WireConversionError("Register allocation size must be nonnegative.", stmt)
    root = frame.push(stmts.AllocRegister(size)).results[0]
    register = Register(root, length)
    frame.own(register)
    return register


def run_library(emit: EmitWire, frame: WireFrame, stmt: func.Invoke) -> Value:
    """Emit the body of a library wrapper in place of its call and return its result.

    The wrapper emits into the caller's block and continues the caller's wires.
    Its allocations live until the caller's region ends.
    """
    # The body reads the caller's integers when it emits an index of a caller
    # location, so the frame has parent access.
    with emit.new_frame(stmt.callee.code, has_parent_access=True) as body:
        body.share(frame, stmt)
        result = emit.frame_call(
            body, stmt.callee.code, WrapperSelf(), *frame.get_values(stmt.inputs)
        )
    return result


def call_converted(
    emit: EmitWire, frame: WireFrame, stmt: func.Invoke, layout: Layout | None = None
) -> Value:
    """Call a converted function and continue its in-out qubits with its results."""
    if any(
        is_subtype(value.type, types.Tuple) and holds_qubits(value.type)
        for value in stmt.inputs
    ):
        raise WireConversionError(
            "Wire calls require separate arguments for tuple fields.", stmt
        )
    callee = stmt.callee.code
    assert isinstance(callee, func.Function)
    layout = Layout.of(callee.signature) if layout is None else layout
    wired = emit.converted[stmt.callee]
    arguments = frame.get_values(stmt.inputs)
    inout = inout_locations(callee, layout, arguments, stmt)
    location_at = dict(zip(layout.inout_positions, inout, strict=True))
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
    for location, result in zip(inout, outputs[count:], strict=True):
        emit.restore(frame, location, result)
    ordinary = outputs[:count]
    if layout.packed:
        return ordinary
    return ordinary[0] if ordinary else frame.push(func.ConstantNone()).results[0]


def inout_locations(
    callee: func.Function,
    layout: Layout,
    arguments: tuple[Value, ...],
    stmt: func.Invoke,
) -> list[Single | Register | View]:
    """Return the quantum call operands, each with the shape that its parameter declares.

    A qubit parameter takes one qubit. A register parameter takes a whole register
    or a step-1 slice of qubits of known length. The callee reads register
    dimensions from its parameter types, so an argument of another shape would make
    it address the wrong qubits.
    """
    parameters = callee.body.blocks[0].args[1:]
    inout: list[Single | Register | View] = []
    for position in layout.inout_positions:
        operand, typ = arguments[position], parameters[position].type
        match operand:
            case Qubit() | Element() if quantum_type(typ) == WireType:
                inout.append(operand)
                continue
            case Register(_, length, row_shape):
                outer = None if length is None else length.constant
                actual = (outer, *row_shape)
            case View(_, Slice(_, 1, length), ()) if length is not None:
                actual = (length.constant,)
            case Qubit() | Element():
                raise WireConversionError(
                    "A register parameter requires a register argument.", stmt
                )
            case _:
                raise WireConversionError(
                    "A call requires whole registers, step-1 slices of known length"
                    " or individual qubits.",
                    stmt,
                )
        if quantum_type(typ) == WireType:
            raise WireConversionError(
                "A qubit parameter requires one qubit argument.", stmt
            )
        expected = register_shape(typ)
        if len(expected) != len(actual) or any(
            size is not None and size != given for size, given in zip(expected, actual)
        ):
            raise WireConversionError(
                "A register argument must provably have the shape that its"
                " parameter declares.",
                stmt,
            )
        inout.append(operand)
    whole = [operand for operand in inout if isinstance(operand, Register)]
    if any(
        other is not register and other.root is register.root
        for register in whole
        for other in inout
    ):
        raise WireConversionError(
            "A call cannot take a whole register together with a qubit or a slice"
            " of the same register.",
            stmt,
        )
    return inout


def call_results(
    frame: WireFrame, result: ir.SSAValue, layout: Layout
) -> tuple[ir.SSAValue, ...]:
    """Split the result of a wire call into one value for each wire result."""
    outputs = layout.result_types(result.type)
    if not outputs:
        return ()
    if len(outputs) == 1:
        return (result,)
    return unpack(frame, result, outputs)


def unpack(
    frame: WireFrame, packed: ir.SSAValue, outputs: tuple[types.TypeAttribute, ...]
) -> tuple[ir.SSAValue, ...]:
    """Read each field of the tuple value `packed` and give it the type in `outputs`."""
    fields: list[ir.SSAValue] = []
    for i, typ in enumerate(outputs):
        index = frame.push(py.Constant(i)).results[0]
        item = frame.push(py.GetItem(packed, index))
        item.results[0].type = typ
        fields.append(item.results[0])
    return tuple(fields)
