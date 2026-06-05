from typing import Sequence
from warnings import warn
from dataclasses import field, dataclass

import cirq
from kirin import ir, types, interp
from kirin.emit import EmitABC, EmitFrame
from kirin.ir.exception import ValidationErrorGroup
from kirin.interp import MethodTable, impl
from kirin.dialects import py, scf, func, ilist
from typing_extensions import Self

from bloqade.squin import kernel
from bloqade.rewrite.passes import AggressiveUnroll

from ..validation import CirqClassicalControlValidation


def emit_circuit(
    mt: ir.Method,
    qubits: Sequence[cirq.Qid] | None = None,
    circuit_qubits: Sequence[cirq.Qid] | None = None,
    args: tuple = (),
    ignore_returns: bool = False,
) -> cirq.Circuit:
    """Converts a squin.kernel method to a cirq.Circuit object.

    Args:
        mt (ir.Method): The kernel method from which to construct the circuit.

    Keyword Args:
        circuit_qubits (Sequence[cirq.Qid] | None):
            A list of qubits to use as the qubits in the circuit. Defaults to None.
            If this is None, then `cirq.LineQubit`s are inserted for every `squin.qalloc`
            statement in the order they appear inside the kernel.
            **Note**: If a list of qubits is provided, make sure that there is a sufficient
            number of qubits for the resulting circuit.
        args (tuple):
            The arguments of the kernel function from which to emit a circuit.
        ignore_returns (bool):
            If `False`, emitting a circuit from a kernel that returns a value will error.
            Set it to `True` in order to ignore the return value(s). Defaults to `False`.

    ## Examples:

    Here's a very basic example:

    ```python
    from bloqade import squin
    from bloqade.cirq_utils import emit_circuit

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    circuit = emit_circuit(main)

    print(circuit)
    ```

    You can also compose multiple kernels. Those are emitted as subcircuits within the "main" circuit.
    Subkernels can accept arguments and return a value.

    ```python
    from bloqade import squin
    from bloqade.cirq_utils import emit_circuit
    from kirin.dialects import ilist
    from typing import Literal
    import cirq

    @squin.kernel
    def entangle(q: ilist.IList[squin.qubit.Qubit, Literal[2]]):
        squin.h(q[0])
        squin.cx(q[0], q[1])

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        q2 = squin.qalloc(3)
        squin.cx(q[1], q2[2])


    # custom list of qubits on grid
    qubits = [cirq.GridQubit(i, i+1) for i in range(5)]

    circuit = emit_circuit(main, circuit_qubits=qubits)
    print(circuit)

    ```

    We also passed in a custom list of qubits above. This allows you to provide a custom geometry
    and manipulate the qubits in other circuits directly written in cirq as well.
    """

    if circuit_qubits is None and qubits is not None:
        circuit_qubits = qubits
        warn(
            "The keyword argument `qubits` is deprecated. Use `circuit_qubits` instead."
        )

    if (
        not ignore_returns
        and isinstance(mt.code, func.Function)
        and not mt.code.signature.output.is_subseteq(types.NoneType)
    ):
        raise interp.exceptions.InterpreterError(
            "The method you are trying to convert to a circuit has a return value, but returning from a circuit is not supported."
            " Set `ignore_returns = True` in order to simply ignore the return values and emit a circuit."
        )

    if len(args) != len(mt.args):
        raise ValueError(
            f"The method from which you're trying to emit a circuit takes {len(mt.args)} as input, but you passed in {len(args)} via the `args` keyword!"
        )

    emitter = EmitCirq(qubits=circuit_qubits)

    symbol_op_trait = mt.code.get_trait(ir.SymbolOpInterface)
    if (symbol_op_trait := mt.code.get_trait(ir.SymbolOpInterface)) is None:
        raise interp.exceptions.InterpreterError(
            "The method is not a symbol, cannot emit circuit!"
        )

    sym_name = symbol_op_trait.get_sym_name(mt.code).unwrap()

    if (signature_trait := mt.code.get_trait(ir.HasSignature)) is None:
        raise interp.exceptions.InterpreterError(
            f"The method {sym_name} does not have a signature, cannot emit circuit!"
        )

    signature = signature_trait.get_signature(mt.code)
    new_signature = func.Signature(inputs=(), output=signature.output)

    callable_region = mt.callable_region.clone()
    entry_block = callable_region.blocks[0]
    args_ssa = list(entry_block.args)
    first_stmt = entry_block.first_stmt

    assert first_stmt is not None, "Method has no statements!"
    if len(args_ssa) - 1 != len(args):
        raise interp.exceptions.InterpreterError(
            f"The method {sym_name} takes {len(args_ssa) - 1} arguments, but you passed in {len(args)} via the `args` keyword!"
        )

    for arg, arg_ssa in zip(args, args_ssa[1:], strict=True):
        (value := py.Constant(arg)).insert_before(first_stmt)
        arg_ssa.replace_by(value.result)
        entry_block.args.delete(arg_ssa)

    new_func = func.Function(
        sym_name=sym_name, body=callable_region, signature=new_signature
    )
    mt_ = ir.Method(
        dialects=mt.dialects,
        code=new_func,
        sym_name=sym_name,
    )

    AggressiveUnroll(mt_.dialects).fixpoint(mt_)

    _, validation_errors = CirqClassicalControlValidation().run(mt_)
    if validation_errors:
        raise ValidationErrorGroup(
            f"Cirq emission validation failed with {len(validation_errors)} error(s)",
            errors=validation_errors,
        )

    emitter.initialize()
    emitter.run(mt_)
    return emitter.circuit


@dataclass(frozen=True)
class CirqMeasurementResult:
    key: cirq.MeasurementKey


@dataclass
class EmitCirqFrame(EmitFrame):
    qubit_index: int = 0
    qubits: Sequence[cirq.Qid] | None = None


def _default_kernel():
    return kernel


@dataclass
class EmitCirq(EmitABC[EmitCirqFrame, cirq.Circuit]):
    keys = ("emit.cirq", "emit.main")
    dialects: ir.DialectGroup = field(default_factory=_default_kernel)
    void = cirq.Circuit()
    qubits: Sequence[cirq.Qid] | None = None
    circuit: cirq.Circuit = field(default_factory=cirq.Circuit)

    def initialize(self) -> Self:
        return super().initialize()

    def initialize_frame(
        self, node: ir.Statement, *, has_parent_access: bool = False
    ) -> EmitCirqFrame:
        return EmitCirqFrame(
            node, has_parent_access=has_parent_access, qubits=self.qubits
        )

    def reset(self):
        self.circuit = cirq.Circuit()

    def eval_fallback(self, frame: EmitCirqFrame, node: ir.Statement) -> tuple:
        return tuple(None for _ in range(len(node.results)))


@func.dialect.register(key="emit.cirq")
class __FuncEmit(MethodTable):

    @impl(func.Function)
    def emit_func(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Function):
        for block in stmt.body.blocks:
            frame.current_block = block
            for s in block.stmts:
                frame.current_stmt = s
                stmt_results = emit.frame_eval(frame, s)
                if isinstance(stmt_results, tuple):
                    if len(stmt_results) != 0:
                        frame.set_values(s.results, stmt_results)
                    continue

        return (emit.circuit,)

    @impl(func.Invoke)
    def emit_invoke(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: func.Invoke):
        raise interp.exceptions.InterpreterError(
            "Function invokes should need to be inlined! "
            "If you called the emit_circuit method, that should have happened, please report this issue."
        )


@py.indexing.dialect.register(key="emit.cirq")
class __Concrete(interp.MethodTable):

    @interp.impl(py.indexing.GetItem)
    def getindex(self, emit: EmitCirq, frame: interp.Frame, stmt: py.indexing.GetItem):
        obj = frame.get(stmt.obj)
        idx = frame.get(stmt.index)
        if isinstance(obj, ilist.IList) and isinstance(idx, int):
            return (obj[idx],)

        return ()

    @interp.impl(py.Constant)
    def emit_constant(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: py.Constant):
        return (stmt.value.data,)  # pyright: ignore[reportAttributeAccessIssue]


@py.cmp.dialect.register(key="emit.cirq")
class __Cmp(interp.MethodTable):
    @interp.impl(py.cmp.Eq)
    def eq(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: py.cmp.Eq):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        if isinstance(lhs, CirqMeasurementResult) and rhs in (0, 1, False, True):
            return (_measurement_condition(lhs, rhs),)

        if isinstance(rhs, CirqMeasurementResult) and lhs in (0, 1, False, True):
            return (_measurement_condition(rhs, lhs),)

        return ()


def _measurement_condition(
    measurement: CirqMeasurementResult, expected: int | bool
) -> cirq.BitMaskKeyCondition:
    target_value = int(expected)
    return cirq.BitMaskKeyCondition(
        measurement.key,
        target_value=target_value,
        equal_target=True,
        bitmask=1,
    )


@ilist.dialect.register(key="emit.cirq")
class __IList(interp.MethodTable):
    @interp.impl(ilist.New)
    def new_ilist(
        self,
        emit: EmitCirq,
        frame: interp.Frame,
        stmt: ilist.New,
    ):
        return (ilist.IList(data=frame.get_values(stmt.values)),)


@scf.dialect.register(key="emit.cirq")
class __Scf(interp.MethodTable):
    @interp.impl(scf.Yield)
    def emit_yield(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: scf.Yield):
        return frame.get_values(stmt.values)

    @interp.impl(scf.IfElse)
    def emit_if_else(self, emit: EmitCirq, frame: EmitCirqFrame, stmt: scf.IfElse):
        condition = frame.get(stmt.cond)
        if not isinstance(condition, cirq.Condition):
            raise interp.InterpreterError(
                "Cannot emit Cirq classical control: if condition is not based on "
                "a supported measurement comparison."
            )

        parent_circuit = emit.circuit
        body_circuit = cirq.Circuit()
        emit.circuit = body_circuit

        try:
            with emit.new_frame(stmt) as then_frame:
                then_frame.entries.update(frame.entries)
                for child in stmt.then_body.blocks[0].stmts:
                    then_frame.current_stmt = child
                    child_results = emit.frame_eval(then_frame, child)
                    if isinstance(child_results, tuple) and len(child_results) != 0:
                        then_frame.set_values(child.results, child_results)
        finally:
            emit.circuit = parent_circuit

        body_ops = list(body_circuit.all_operations())
        if len(body_ops) != 1:
            raise interp.InterpreterError(
                "Cannot emit Cirq classical control: then-body must emit exactly "
                "one Cirq operation."
            )

        emit.circuit.append(body_ops[0].with_classical_controls(condition))

        term = stmt.then_body.blocks[0].last_stmt
        if isinstance(term, scf.Yield):
            return then_frame.get_values(term.values)

        return ()
