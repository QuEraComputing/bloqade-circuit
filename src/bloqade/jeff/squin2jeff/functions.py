"""This module holds the rules that emit jeff calls and returns."""

from kirin import ir, interp
from kirin.dialects import func

from bloqade.qubit import stmts as qubit_stmts, qalloc
from bloqade.jeff.forms import GATE_KERNELS, QUBIT_KERNELS, is_library
from bloqade.jeff.dialects import stmts
from bloqade.analysis.reference import (
    Whole,
    Register,
    Untracked,
    roots,
    positions,
)
from bloqade.jeff.dialects.stmts.call import declared_outputs

from .linearize import KEY, Frame, Value, Linearize, jeff_kind


@func.dialect.register(key=KEY)
class _Func(interp.MethodTable):
    """A method table that emits calls and returns."""

    @interp.impl(func.Function)
    def function(
        self, emit: Linearize, frame: Frame, stmt: func.Function
    ) -> interp.StatementResult[Value]:
        """Fill the body of the jeff method of the kernel copy `stmt`."""
        method = emit.declare(stmt)
        frame.body = block = method.callable_region.blocks[0]
        args: list[Value] = []
        for param, arg in zip(stmt.body.blocks[0].args, block.args, strict=True):
            match emit.refs[param]:
                case Whole(root) | Register(root):
                    frame.wires[root] = arg
                    args.append(None)
                case Untracked():
                    args.append(arg)
                case _:
                    args.append(None)
        emit.frame_call(frame, stmt, *args)
        return ()

    @interp.impl(func.ConstantNone)
    def none(
        self, emit: Linearize, frame: Frame, stmt: func.ConstantNone
    ) -> interp.StatementResult[Value]:
        """Give `None` no jeff value."""
        return (None,)

    @interp.impl(func.Invoke)
    def invoke(
        self, emit: Linearize, frame: Frame, stmt: func.Invoke
    ) -> interp.StatementResult[Value]:
        """Emit a library kernel as its jeff statements, and any other as a call."""
        if is_library(stmt.callee):
            return self.library(emit, frame, stmt)
        return self.call(emit, frame, stmt)

    def library(
        self, emit: Linearize, frame: Frame, stmt: func.Invoke
    ) -> interp.StatementResult[Value]:
        """Emit the jeff statements of the library kernel that `stmt` calls.

        A gate kernel applies its gate to each qubit, or group of qubits, of its
        operands. `qalloc` becomes one register allocation.
        """
        if (form := GATE_KERNELS.get(stmt.callee)) is not None:
            angles = [frame.scalar(a) for a in stmt.inputs[: form.angles]]
            emit.gate(frame, form, stmt.inputs[form.angles :], angles, form.adjoint)
            return (None,)
        match QUBIT_KERNELS.get(stmt.callee):
            case qubit_stmts.New:
                (root,) = roots(emit.refs[stmt.result])
                frame.wires[root] = frame.push(stmts.Alloc()).result
                return (None,)
            case qubit_stmts.Reset:
                emit.reset_qubits(frame, stmt.inputs[0])
                return (None,)
            case qubit_stmts.Measure:
                return (emit.measure(frame, stmt.inputs[0]),)
            case qubit_stmts.IsOne:
                return (frame.value(stmt.inputs[0]),)
            case qubit_stmts.IsZero:
                return (emit.negate(frame, stmt.inputs[0]),)
        if stmt.callee is not qalloc:
            raise interp.InterpreterError(f"{stmt.callee.sym_name} has no jeff form")
        register = frame.push(stmts.RegAlloc(frame.scalar(stmt.inputs[0])))
        register.result.type = jeff_kind(stmt.result.type)
        (root,) = roots(emit.refs[stmt.result])
        frame.wires[root] = register.result
        return (None,)

    def call(
        self, emit: Linearize, frame: Frame, stmt: func.Invoke
    ) -> interp.StatementResult[Value]:
        """Emit a jeff call of the user kernel that `stmt` calls.

        `Layout` gives the order of the outputs. Each handed-back wire becomes the
        current wire of its argument. An output of a returned position is a
        classical value or the wire of a qubit that the callee returns.
        """
        code = stmt.callee.code
        if not isinstance(code, func.Function):
            raise interp.InterpreterError(f"{stmt.callee.sym_name} is not a function")
        if code not in emit.functions:
            emit.callable_to_emit.append(code)
        callee = emit.declare(code)
        layout = emit.layout(code)
        passed = [emit.refs[arg] for arg in stmt.inputs]
        inputs = tuple(
            frame.scalar(arg) if isinstance(ref, Untracked) else emit.take(frame, ref)
            for arg, ref in zip(stmt.inputs, passed)
        )
        qubits = [ref for ref in passed if not isinstance(ref, Untracked)]
        call = frame.push(
            stmts.Call(callee, inputs, declared_outputs(callee.return_type))
        )
        for ref, wire in zip(qubits, call.results[: len(qubits)], strict=True):
            emit.give(frame, ref, wire)
        if not layout.return_types:
            return (None,)
        # A constant tuple has one reference for all its positions.
        result = emit.refs[stmt.result]
        refs = positions(result, len(layout.return_types))
        values: list[Value] = [None] * len(refs)
        for p, extra in zip(layout.returned, call.results[len(qubits) :], strict=True):
            if isinstance(refs[p], Untracked):
                values[p] = extra
            else:
                emit.give(frame, refs[p], extra)
        return (tuple(values) if len(values) > 1 else values[0],)

    @interp.impl(func.Return)
    def return_(
        self, emit: Linearize, frame: Frame, stmt: func.Return
    ) -> interp.ReturnValue[Value]:
        """End the function with the outputs in the order that `Layout` gives.

        The handed-back wires come first, then the outputs of the returned
        positions. The function frees the wires of every other root.
        """
        code = stmt.parent_stmt
        if not isinstance(code, func.Function):
            raise interp.InterpreterError("a return outside a function")
        layout = emit.layout(code)
        handed = [frame.wires[p] for p in layout.handed_back]
        result = emit.refs[stmt.value]
        value = frame.value(stmt.value)
        values = value if isinstance(value, tuple) else (value,)
        refs = positions(result, len(values))
        rest: list[ir.SSAValue] = []
        for p in layout.returned:
            given = values[p]
            if isinstance(given, ir.SSAValue):
                rest.append(emit.fitted(frame, given, layout.return_types[p]))
            elif not isinstance(refs[p], Untracked):
                rest.append(emit.take(frame, refs[p]))
        emit.free(frame, [*layout.handed_back, *roots(result)])
        frame.push(stmts.Return(*handed, *rest))
        return interp.ReturnValue(None)
