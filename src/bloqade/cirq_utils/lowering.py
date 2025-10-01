from typing import Any
from dataclasses import field, dataclass

import cirq
from kirin import ir, types, lowering
from kirin.rewrite import Walk, CFGCompactify
from kirin.dialects import py, scf, func, ilist

from bloqade.squin import qubit, kernel, clifford


def load_circuit(
    circuit: cirq.Circuit,
    kernel_name: str = "main",
    dialects: ir.DialectGroup = kernel,
    register_as_argument: bool = False,
    return_register: bool = False,
    register_argument_name: str = "q",
    globals: dict[str, Any] | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
):
    """Converts a cirq.Circuit object into a squin kernel.

    Args:
        circuit (cirq.Circuit): The circuit to load.

    Keyword Args:
        kernel_name (str): The name of the kernel to load. Defaults to "main".
        dialects (ir.DialectGroup | None): The dialects to use. Defaults to `squin.kernel`.
        register_as_argument (bool): Determine whether the resulting kernel function should accept
            a single `ilist.IList[Qubit, Any]` argument that is a list of qubits used within the
            function. This allows you to compose kernel functions generated from circuits.
            Defaults to `False`.
        return_register (bool): Determine whether the resulting kernel functionr returns a
            single value of type `ilist.IList[Qubit, Any]` that is the list of qubits used
            in the kernel function. Useful when you want to compose multiple kernel functions
            generated from circuits. Defaults to `False`.
        register_argument_name (str): The name of the argument that represents the qubit register.
            Only used when `register_as_argument=True`. Defaults to "q".
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.

    ## Usage Examples:

    ```python
    # from cirq's "hello qubit" example
    import cirq
    from bloqade import squin

    # Pick a qubit.
    qubit = cirq.GridQubit(0, 0)

    # Create a circuit.
    circuit = cirq.Circuit(
        cirq.X(qubit)**0.5,  # Square root of NOT.
        cirq.measure(qubit, key='m')  # Measurement.
    )

    # load the circuit as squin
    main = squin.load_circuit(circuit)

    # print the resulting IR
    main.print()
    ```

    You can also compose kernel functions generated from circuits by passing in
    and / or returning the respective quantum registers:

    ```python
    q = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(cirq.H(q[0]), cirq.CX(*q))

    get_entangled_qubits = squin.cirq.load_circuit(
        circuit, return_register=True, kernel_name="get_entangled_qubits"
    )
    get_entangled_qubits.print()

    entangle_qubits = squin.cirq.load_circuit(
        circuit, register_as_argument=True, kernel_name="entangle_qubits"
    )

    @squin.kernel
    def main():
        qreg = get_entangled_qubits()
        qreg2 = squin.qubit.new(1)
        entangle_qubits([qreg[1], qreg2[0]])
        return squin.qubit.measure(qreg2)
    ```
    """

    target = Squin(dialects=dialects, circuit=circuit)
    body = target.run(
        circuit,
        source=str(circuit),  # TODO: proper source string
        file=file,
        globals=globals,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
        register_as_argument=register_as_argument,
        register_argument_name=register_argument_name,
    )

    if return_register:
        return_value = target.qreg
    else:
        return_value = func.ConstantNone()
        body.blocks[0].stmts.append(return_value)

    return_node = func.Return(value_or_stmt=return_value)
    body.blocks[0].stmts.append(return_node)

    self_arg_name = kernel_name + "_self"
    arg_names = [self_arg_name]
    if register_as_argument:
        args = (target.qreg.type,)
        arg_names.append(register_argument_name)
    else:
        args = ()

    # NOTE: add _self as argument; need to know signature before so do it after lowering
    signature = func.Signature(args, return_node.value.type)
    body.blocks[0].args.insert_from(
        0,
        types.Generic(ir.Method, types.Tuple.where(signature.inputs), signature.output),
        self_arg_name,
    )

    code = func.Function(
        sym_name=kernel_name,
        signature=signature,
        body=body,
    )

    return ir.Method(
        mod=None,
        py_func=None,
        sym_name=kernel_name,
        arg_names=arg_names,
        dialects=dialects,
        code=code,
    )


CirqNode = (
    cirq.Circuit
    | cirq.FrozenCircuit
    | cirq.Moment
    | cirq.Gate
    | cirq.Qid
    | cirq.Operation
)

DecomposeNode = (
    cirq.SwapPowGate
    | cirq.ISwapPowGate
    | cirq.PhasedXPowGate
    | cirq.PhasedXZGate
    | cirq.CSwapGate
    | cirq.XXPowGate
    | cirq.YYPowGate
    | cirq.ZZPowGate
    | cirq.CCXPowGate
    | cirq.CCZPowGate
)


@dataclass
class Squin(lowering.LoweringABC[cirq.Circuit]):
    """Lower a cirq.Circuit object to a squin kernel"""

    circuit: cirq.Circuit
    qreg: ir.SSAValue = field(init=False)
    qreg_index: dict[cirq.Qid, int] = field(init=False, default_factory=dict)
    next_qreg_index: int = field(init=False, default=0)

    def __post_init__(self):
        # TODO: sort by cirq ordering
        qbits = sorted(self.circuit.all_qubits())
        self.qreg_index = {qid: idx for (idx, qid) in enumerate(qbits)}

    def lower_qubit_getindex(self, state: lowering.State[cirq.Circuit], qid: cirq.Qid):
        index = self.qreg_index[qid]
        index_ssa = state.current_frame.push(py.Constant(index)).result
        qbit_getitem = state.current_frame.push(py.GetItem(self.qreg, index_ssa))
        return qbit_getitem.result

    def lower_qubit_getindices(
        self, state: lowering.State[cirq.Circuit], qids: tuple[cirq.Qid, ...]
    ):
        qbits_getitem = [self.lower_qubit_getindex(state, qid) for qid in qids]
        qbits = state.current_frame.push(ilist.New(values=qbits_getitem))
        return qbits.result

    def run(
        self,
        stmt: cirq.Circuit,
        *,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
        register_as_argument: bool = False,
        register_argument_name: str = "q",
    ) -> ir.Region:

        state = lowering.State(
            self,
            file=file,
            lineno_offset=lineno_offset,
            col_offset=col_offset,
        )

        with state.frame([stmt], globals=globals, finalize_next=False) as frame:

            # NOTE: need a register of qubits before lowering statements
            if register_as_argument:
                # NOTE: register as argument to the kernel; we have freedom of choice for the name here
                frame.curr_block.args.append_from(
                    ilist.IListType[qubit.QubitType, types.Any],
                    name=register_argument_name,
                )
                self.qreg = frame.curr_block.args[0]
            else:
                # NOTE: create a new register of appropriate size
                n_qubits = len(self.qreg_index)
                n = frame.push(py.Constant(n_qubits))
                self.qreg = frame.push(qubit.New(n_qubits=n.result)).result

            self.visit(state, stmt)

            if compactify:
                Walk(CFGCompactify()).rewrite(frame.curr_region)

            region = frame.curr_region

        return region

    def visit(
        self, state: lowering.State[cirq.Circuit], node: CirqNode
    ) -> lowering.Result:
        name = node.__class__.__name__
        return getattr(self, f"visit_{name}", self.generic_visit)(state, node)

    def generic_visit(self, state: lowering.State[cirq.Circuit], node: CirqNode):
        if isinstance(node, CirqNode):
            raise lowering.BuildError(
                f"Cannot lower {node.__class__.__name__} node: {node}"
            )
        raise lowering.BuildError(f"Cannot lower {node}")

        # return self.visit_Operation(state, node)

    def lower_literal(self, state: lowering.State[cirq.Circuit], value) -> ir.SSAValue:
        raise lowering.BuildError("Literals not supported in cirq circuit")

    def lower_global(
        self, state: lowering.State[cirq.Circuit], node: CirqNode
    ) -> lowering.LoweringABC.Result:
        raise lowering.BuildError("Literals not supported in cirq circuit")

    def visit_Circuit(
        self,
        state: lowering.State[cirq.Circuit],
        node: cirq.Circuit | cirq.FrozenCircuit,
    ) -> lowering.Result:
        for moment in node:
            self.visit_Moment(state, moment)

    def visit_Moment(
        self, state: lowering.State[cirq.Circuit], node: cirq.Moment
    ) -> lowering.Result:
        for op_ in node.operations:
            self.visit(state, op_)

    def visit_GateOperation(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        if isinstance(node.gate, DecomposeNode):
            # NOTE: easier to decompose these, but for that we need the qubits too,
            # so we need to do this within this method
            for subnode in cirq.decompose_once(node):
                self.visit(state, subnode)
            return

        # NOTE: just forward to the appropriate method by getting the name
        name = node.gate.__class__.__name__
        return getattr(self, f"visit_{name}", self.generic_visit)(state, node)

    def visit_TaggedOperation(
        self, state: lowering.State[cirq.Circuit], node: cirq.TaggedOperation
    ):
        return self.visit(state, node.untagged)

    def visit_ClassicallyControlledOperation(
        self,
        state: lowering.State[cirq.Circuit],
        node: cirq.ClassicallyControlledOperation,
    ):
        conditions: list[ir.SSAValue] = []
        for outcome in node.classical_controls:
            key = outcome.key
            if isinstance(key, cirq.MeasurementKey):
                key = key.name
            measurement_outcome = state.current_frame.defs[key]

            if measurement_outcome.type.is_subseteq(ilist.IListType):
                # NOTE: there is currently no convenient ilist.any method, so we need to use foldl
                # with a simple function that just does an or

                def bool_op_or(x: bool, y: bool) -> bool:
                    return x or y

                f_code = state.current_frame.push(
                    lowering.Python(self.dialects).python_function(bool_op_or)
                )
                fn = ir.Method(
                    mod=None,
                    py_func=bool_op_or,
                    sym_name="bool_op_or",
                    arg_names=[],
                    dialects=self.dialects,
                    code=f_code,
                )
                f_const = state.current_frame.push(py.constant.Constant(fn))
                init_val = state.current_frame.push(py.Constant(False)).result
                condition = state.current_frame.push(
                    ilist.Foldl(f_const.result, measurement_outcome, init=init_val)
                ).result
            else:
                condition = measurement_outcome

            conditions.append(condition)

        if len(conditions) == 1:
            condition = conditions[0]
        else:
            condition = state.current_frame.push(
                py.boolop.And(conditions[0], conditions[1])
            ).result
            for next_cond in conditions[2:]:
                condition = state.current_frame.push(
                    py.boolop.And(condition, next_cond)
                ).result

        then_stmt = self.visit(state, node.without_classical_controls())

        assert isinstance(
            then_stmt, ir.Statement
        ), f"Expected operation of classically controlled node {node} to be lowered to a statement, got type {type(then_stmt)}. \
        Please report this issue!"

        # NOTE: remove stmt from parent block
        then_stmt.detach()
        then_body = ir.Block((then_stmt,))

        return state.current_frame.push(scf.IfElse(condition, then_body=then_body))

    def visit_MeasurementGate(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        cirq_qubits = node.qubits
        if len(cirq_qubits) == 1:
            qbit = self.lower_qubit_getindex(state, node.qubits[0])
            stmt = state.current_frame.push(qubit.MeasureQubit(qbit))
        else:
            qubits = self.lower_qubit_getindices(state, node.qubits)
            stmt = state.current_frame.push(qubit.MeasureQubitList(qubits))

        # NOTE: add for classically controlled lowering
        key = node.gate.key
        if isinstance(key, cirq.MeasurementKey):
            key = key.name
        state.current_frame.defs[key] = stmt.result

        return stmt

    def visit_SingleQubitPauliStringGateOperation(
        self,
        state: lowering.State[cirq.Circuit],
        node: cirq.SingleQubitPauliStringGateOperation,
    ):
        if isinstance(node.pauli, cirq.IdentityGate):
            # TODO: do we need an identity gate in clifford?
            return

        qargs = self.lower_qubit_getindices(state, (node.qubit,))
        match node.pauli:
            case cirq.X:
                clifford_stmt = clifford.stmts.X
            case cirq.Y:
                clifford_stmt = clifford.stmts.Y
            case cirq.Z:
                clifford_stmt = clifford.stmts.Z
            case _:
                raise lowering.BuildError(f"Unexpected Pauli operation {node.pauli}")

        return state.current_frame.push(clifford_stmt(qargs))

    def visit_HPowGate(self, state: lowering.State[cirq.Circuit], node: cirq.HPowGate):
        qargs = self.lower_qubit_getindices(state, node.qubits)

        if node.gate.exponent % 2 == 1:
            return state.current_frame.push(clifford.stmts.H(qargs))

        # NOTE: decompose into products of paulis for arbitrary exponents according to _decompose_ method
        for subnode in cirq.decompose_once(node):
            self.visit(state, subnode)

    def visit_XPowGate(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        qargs = self.lower_qubit_getindices(state, node.qubits)
        if node.gate.exponent % 2 == 1:
            return state.current_frame.push(clifford.stmts.X(qargs))

        angle = state.current_frame.push(py.Constant(0.5 * node.gate.exponent))
        return state.current_frame.push(clifford.stmts.Rx(angle.result, qargs))

    def visit_YPowGate(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        qargs = self.lower_qubit_getindices(state, node.qubits)
        if node.gate.exponent % 2 == 1:
            return state.current_frame.push(clifford.stmts.Y(qargs))

        angle = state.current_frame.push(py.Constant(0.5 * node.gate.exponent))
        return state.current_frame.push(clifford.stmts.Ry(angle.result, qargs))

    def visit_ZPowGate(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        qargs = self.lower_qubit_getindices(state, node.qubits)

        if abs(node.gate.exponent) == 0.5:
            adjoint = node.gate.exponent < 0
            return state.current_frame.push(
                clifford.stmts.S(adjoint=adjoint, qubits=qargs)
            )

        if abs(node.gate.exponent) == 0.25:
            adjoint = node.gate.exponent < 0
            return state.current_frame.push(
                clifford.stmts.T(adjoint=adjoint, qubits=qargs)
            )

        if node.gate.exponent % 2 == 1:
            return state.current_frame.push(clifford.stmts.Z(qubits=qargs))

        angle = state.current_frame.push(py.Constant(0.5 * node.gate.exponent))
        return state.current_frame.push(clifford.stmts.Rz(angle.result, qargs))

    def visit_Rx(self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation):
        qargs = self.lower_qubit_getindices(state, node.qubits)
        angle = state.current_frame.push(py.Constant(value=0.5 * node.gate.exponent))
        return state.current_frame.push(clifford.stmts.Rx(angle.result, qargs))

    def visit_Ry(self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation):
        qargs = self.lower_qubit_getindices(state, node.qubits)
        angle = state.current_frame.push(py.Constant(value=0.5 * node.gate.exponent))
        return state.current_frame.push(clifford.stmts.Ry(angle.result, qargs))

    def visit_Rz(self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation):
        qargs = self.lower_qubit_getindices(state, node.qubits)
        angle = state.current_frame.push(py.Constant(value=0.5 * node.gate.exponent))
        return state.current_frame.push(clifford.stmts.Rz(angle.result, qargs))

    def visit_CXPowGate(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        if node.gate.exponent % 2 == 0:
            return

        if node.gate.exponent % 2 != 1:
            raise lowering.BuildError("Exponents of CX gate are not supported!")

        control, target = node.qubits
        control_qarg = self.lower_qubit_getindices(state, (control,))
        target_qarg = self.lower_qubit_getindices(state, (target,))
        return state.current_frame.push(
            clifford.stmts.CX(controls=control_qarg, targets=target_qarg)
        )

    def visit_CZPowGate(
        self, state: lowering.State[cirq.Circuit], node: cirq.GateOperation
    ):
        if node.gate.exponent % 2 == 0:
            return

        if node.gate.exponent % 2 != 1:
            raise lowering.BuildError("Exponents of CZ gate are not supported!")

        control, target = node.qubits
        control_qarg = self.lower_qubit_getindices(state, (control,))
        target_qarg = self.lower_qubit_getindices(state, (target,))
        return state.current_frame.push(
            clifford.stmts.CZ(controls=control_qarg, targets=target_qarg)
        )

    def visit_ControlledOperation(
        self, state: lowering.State[cirq.Circuit], node: cirq.ControlledOperation
    ):
        match node.gate.sub_gate:
            case cirq.X:
                stmt = clifford.stmts.CX
            case cirq.Y:
                stmt = clifford.stmts.CY
            case cirq.Z:
                stmt = clifford.stmts.CZ
            case _:
                raise lowering.BuildError(
                    f"Cannot lowering controlled operation: {node}"
                )

        control, target = node.qubits
        control_qarg = self.lower_qubit_getindices(state, (control,))
        target_qarg = self.lower_qubit_getindices(state, (target,))
        return state.current_frame.push(stmt(control_qarg, target_qarg))

    def visit_FrozenCircuit(
        self, state: lowering.State[cirq.Circuit], node: cirq.FrozenCircuit
    ):
        return self.visit_Circuit(state, node)

    def visit_CircuitOperation(
        self, state: lowering.State[cirq.Circuit], node: cirq.CircuitOperation
    ):
        reps = node.repetitions

        if not isinstance(reps, int):
            raise lowering.BuildError(
                f"Cannot lower CircuitOperation with non-integer repetitions: {node}"
            )

        if reps > 1:
            raise lowering.BuildError(
                "Repetitions of circuit operatiosn not yet supported"
            )

        return self.visit(state, node.circuit)

    # def visit_BitFlipChannel(
    #     self, state: lowering.State[cirq.Circuit], node: cirq.BitFlipChannel
    # ):
    #     x = state.current_frame.push(op.stmts.X())
    #     p = state.current_frame.push(py.Constant(node.p))
    #     return state.current_frame.push(
    #         noise.stmts.PauliError(basis=x.result, p=p.result)
    #     )

    # def visit_AmplitudeDampingChannel(
    #     self, state: lowering.State[cirq.Circuit], node: cirq.AmplitudeDampingChannel
    # ):
    #     r = state.current_frame.push(op.stmts.Reset())
    #     p = state.current_frame.push(py.Constant(node.gamma))

    #     # TODO: do we need a dedicated noise stmt for this? Using PauliError
    #     # with this basis feels like a hack
    #     noise_channel = state.current_frame.push(
    #         noise.stmts.PauliError(basis=r.result, p=p.result)
    #     )

    #     return noise_channel

    # def visit_GeneralizedAmplitudeDampingChannel(
    #     self,
    #     state: lowering.State[cirq.Circuit],
    #     node: cirq.GeneralizedAmplitudeDampingChannel,
    # ):
    #     p = state.current_frame.push(py.Constant(node.p)).result
    #     gamma = state.current_frame.push(py.Constant(node.gamma)).result

    #     # NOTE: cirq has a weird convention here: if p == 1, we have AmplitudeDampingChannel,
    #     # which basically means p is the probability of the environment being in the vacuum state
    #     prob0 = state.current_frame.push(py.binop.Mult(p, gamma)).result
    #     one_ = state.current_frame.push(py.Constant(1)).result
    #     p_minus_1 = state.current_frame.push(py.binop.Sub(one_, p)).result
    #     prob1 = state.current_frame.push(py.binop.Mult(p_minus_1, gamma)).result

    #     r0 = state.current_frame.push(op.stmts.Reset()).result
    #     r1 = state.current_frame.push(op.stmts.ResetToOne()).result

    #     probs = state.current_frame.push(ilist.New(values=(prob0, prob1))).result
    #     ops = state.current_frame.push(ilist.New(values=(r0, r1))).result

    #     noise_channel = state.current_frame.push(
    #         noise.stmts.StochasticUnitaryChannel(probabilities=probs, operators=ops)
    #     )

    #     return noise_channel

    # def visit_DepolarizingChannel(
    #     self, state: lowering.State[cirq.Circuit], node: cirq.DepolarizingChannel
    # ):
    #     p = state.current_frame.push(py.Constant(node.p)).result
    #     return state.current_frame.push(noise.stmts.Depolarize(p))

    # def visit_AsymmetricDepolarizingChannel(
    #     self, state: lowering.State[cirq.Circuit], node: cirq.AsymmetricDepolarizingChannel
    # ):
    #     nqubits = node.num_qubits()
    #     if nqubits > 2:
    #         raise lowering.BuildError(
    #             "AsymmetricDepolarizingChannel applied to more than 2 qubits is not supported!"
    #         )

    #     if nqubits == 1:
    #         p_x = state.current_frame.push(py.Constant(node.p_x)).result
    #         p_y = state.current_frame.push(py.Constant(node.p_y)).result
    #         p_z = state.current_frame.push(py.Constant(node.p_z)).result
    #         params = state.current_frame.push(ilist.New(values=(p_x, p_y, p_z))).result
    #         return state.current_frame.push(noise.stmts.SingleQubitPauliChannel(params))

    #     # NOTE: nqubits == 2
    #     error_probs = node.error_probabilities
    #     paulis = ("I", "X", "Y", "Z")
    #     values = []
    #     for p1 in paulis:
    #         for p2 in paulis:
    #             if p1 == p2 == "I":
    #                 continue

    #             p = error_probs.get(p1 + p2, 0.0)
    #             p_ssa = state.current_frame.push(py.Constant(p)).result
    #             values.append(p_ssa)

    #     params = state.current_frame.push(ilist.New(values=values)).result
    #     return state.current_frame.push(noise.stmts.TwoQubitPauliChannel(params))
