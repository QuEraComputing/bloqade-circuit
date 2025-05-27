import math
from typing import Any
from dataclasses import field, dataclass

import cirq
from kirin import ir, lowering
from kirin.rewrite import Walk, CFGCompactify
from kirin.dialects import py, ilist

from .. import op, noise, qubit

CirqNode = cirq.Circuit | cirq.Moment | cirq.Gate | cirq.Qid | cirq.Operation

DecomposeNode = (
    cirq.SwapPowGate
    | cirq.ISwapPowGate
    | cirq.PhasedXPowGate
    | cirq.PhasedXZGate
    | cirq.CSwapGate
)


@dataclass
class Squin(lowering.LoweringABC[CirqNode]):
    """Lower a cirq.Circuit object to a squin kernel"""

    circuit: cirq.Circuit
    qreg: qubit.New = field(init=False)
    qreg_index: dict[cirq.Qid, int] = field(init=False, default_factory=dict)
    next_qreg_index: int = field(init=False, default=0)

    def lower_qubit_getindex(self, state: lowering.State[CirqNode], qid: cirq.Qid):
        index = self.qreg_index.get(qid)

        if index is None:
            index = self.next_qreg_index
            self.qreg_index[qid] = index
            self.next_qreg_index += 1

        index_ssa = state.current_frame.push(py.Constant(index)).result
        qbit_getitem = state.current_frame.push(py.GetItem(self.qreg.result, index_ssa))
        return qbit_getitem.result

    def lower_qubit_getindices(
        self, state: lowering.State[CirqNode], qids: list[cirq.Qid]
    ):
        qbits_getitem = [self.lower_qubit_getindex(state, qid) for qid in qids]
        qbits_stmt = ilist.New(values=qbits_getitem)
        qbits_result = state.current_frame.get(qbits_stmt.name)

        if qbits_result is not None:
            return qbits_result

        state.current_frame.push(qbits_stmt)
        return qbits_stmt.result

    def run(
        self,
        stmt: CirqNode,
        *,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> ir.Region:

        state = lowering.State(
            self,
            file=file,
            lineno_offset=lineno_offset,
            col_offset=col_offset,
        )

        with state.frame(
            [stmt],
            globals=globals,
            finalize_next=False,
        ) as frame:
            # NOTE: create a global register of qubits first
            # TODO: can there be a circuit without qubits?
            n_qubits = cirq.num_qubits(self.circuit)
            n = frame.push(py.Constant(n_qubits))
            self.qreg = frame.push(qubit.New(n_qubits=n.result))

            self.visit(state, stmt)

            if compactify:
                Walk(CFGCompactify()).rewrite(frame.curr_region)

            region = frame.curr_region

        return region

    def visit(self, state: lowering.State[CirqNode], node: CirqNode) -> lowering.Result:
        name = node.__class__.__name__
        return getattr(self, f"visit_{name}", self.generic_visit)(state, node)

    def generic_visit(self, state: lowering.State[CirqNode], node: CirqNode):
        if isinstance(node, CirqNode):
            raise lowering.BuildError(
                f"Cannot lower {node.__class__.__name__} node: {node}"
            )
        raise lowering.BuildError(
            f"Unexpected `{node.__class__.__name__}` node: {repr(node)} is not an AST node"
        )

    def lower_literal(self, state: lowering.State[CirqNode], value) -> ir.SSAValue:
        raise lowering.BuildError("Literals not supported in cirq circuit")

    def lower_global(
        self, state: lowering.State[CirqNode], node: CirqNode
    ) -> lowering.LoweringABC.Result:
        raise lowering.BuildError("Literals not supported in cirq circuit")

    def visit_Circuit(
        self, state: lowering.State[CirqNode], node: cirq.Circuit
    ) -> lowering.Result:
        for moment in node:
            state.lower(moment)

    def visit_Moment(
        self, state: lowering.State[CirqNode], node: cirq.Moment
    ) -> lowering.Result:
        for op_ in node.operations:
            state.lower(op_)

    def visit_GateOperation(
        self, state: lowering.State[CirqNode], node: cirq.GateOperation
    ):
        if isinstance(node.gate, cirq.MeasurementGate):
            # NOTE: special dispatch here, since measurement is a gate + a qubit in cirq,
            # but a single statement in squin
            return self.lower_measurement(state, node)

        if isinstance(node.gate, DecomposeNode):
            # NOTE: easier to decompose these, but for that we need the qubits too,
            # so we need to do this within this method
            for subnode in cirq.decompose_once(node):
                state.lower(subnode)
            return

        op_ = state.lower(node.gate).expect_one()
        qbits = self.lower_qubit_getindices(state, node.qubits)
        return state.current_frame.push(qubit.Apply(operator=op_, qubits=qbits))

    def lower_measurement(
        self, state: lowering.State[CirqNode], node: cirq.GateOperation
    ):
        if len(node.qubits) == 1:
            qbit = self.lower_qubit_getindex(state, node.qubits[0])
            return state.current_frame.push(qubit.MeasureQubit(qbit))

        qbits = self.lower_qubit_getindices(state, node.qubits)
        return state.current_frame.push(qubit.MeasureQubitList(qbits))

    def visit_SingleQubitPauliStringGateOperation(
        self,
        state: lowering.State[CirqNode],
        node: cirq.SingleQubitPauliStringGateOperation,
    ):

        match node.pauli:
            case cirq.X:
                op_ = op.stmts.X()
            case cirq.Y:
                op_ = op.stmts.Y()
            case cirq.Z:
                op_ = op.stmts.Z()
            case cirq.I:
                op_ = op.stmts.Identity(sites=1)
            case _:
                raise lowering.BuildError(f"Unexpected Pauli operation {node.pauli}")

        state.current_frame.push(op_)
        qargs = self.lower_qubit_getindices(state, [node.qubit])
        return state.current_frame.push(qubit.Apply(op_.result, qargs))

    def visit_HPowGate(self, state: lowering.State[CirqNode], node: cirq.HPowGate):
        if node.exponent == 1:
            return state.current_frame.push(op.stmts.H())

        return state.lower(node.in_su2())

    def visit_XPowGate(self, state: lowering.State[CirqNode], node: cirq.XPowGate):
        if node.exponent == 1:
            return state.current_frame.push(op.stmts.X())

        return self.visit(state, node.in_su2())

    def visit_YPowGate(self, state: lowering.State[CirqNode], node: cirq.YPowGate):
        if node.exponent == 1:
            return state.current_frame.push(op.stmts.Y())

        return self.visit(state, node.in_su2())

    def visit_ZPowGate(self, state: lowering.State[CirqNode], node: cirq.ZPowGate):
        if node.exponent == 0.5:
            return state.current_frame.push(op.stmts.S())

        if node.exponent == 0.25:
            return state.current_frame.push(op.stmts.T())

        if node.exponent == 1:
            return state.current_frame.push(op.stmts.Z())

        # NOTE: just for the Z gate, an arbitrary exponent is equivalent to the ShiftOp
        t = node.exponent
        theta = state.current_frame.push(py.Constant(math.pi * t))
        return state.current_frame.push(op.stmts.ShiftOp(theta=theta.result))

    def visit_Rx(self, state: lowering.State[CirqNode], node: cirq.Rx):
        x = state.current_frame.push(op.stmts.X())
        angle = state.current_frame.push(py.Constant(value=math.pi * node.exponent))
        return state.current_frame.push(op.stmts.Rot(axis=x.result, angle=angle.result))

    def visit_Ry(self, state: lowering.State[CirqNode], node: cirq.Ry):
        y = state.current_frame.push(op.stmts.Y())
        angle = state.current_frame.push(py.Constant(value=math.pi * node.exponent))
        return state.current_frame.push(op.stmts.Rot(axis=y.result, angle=angle.result))

    def visit_Rz(self, state: lowering.State[CirqNode], node: cirq.Rz):
        z = state.current_frame.push(op.stmts.Z())
        angle = state.current_frame.push(py.Constant(value=math.pi * node.exponent))
        return state.current_frame.push(op.stmts.Rot(axis=z.result, angle=angle.result))

    def visit_CXPowGate(self, state: lowering.State[CirqNode], node: cirq.CXPowGate):
        x = state.lower(cirq.XPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Control(x, n_controls=1))

    def visit_CZPowGate(self, state: lowering.State[CirqNode], node: cirq.CZPowGate):
        z = state.lower(cirq.ZPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Control(z, n_controls=1))

    def visit_ControlledOperation(
        self, state: lowering.State[CirqNode], node: cirq.ControlledOperation
    ):
        return self.visit_GateOperation(state, node)

    def visit_ControlledGate(
        self, state: lowering.State[CirqNode], node: cirq.ControlledGate
    ):
        op_ = state.lower(node.sub_gate).expect_one()
        n_controls = node.num_controls()
        return state.current_frame.push(op.stmts.Control(op_, n_controls=n_controls))

    def visit_XXPowGate(self, state: lowering.State[CirqNode], node: cirq.XXPowGate):
        x = state.lower(cirq.XPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Kron(x, x))

    def visit_YYPowGate(self, state: lowering.State[CirqNode], node: cirq.YYPowGate):
        y = state.lower(cirq.YPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Kron(y, y))

    def visit_ZZPowGate(self, state: lowering.State[CirqNode], node: cirq.ZZPowGate):
        z = state.lower(cirq.ZPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Kron(z, z))

    def visit_CCXPowGate(self, state: lowering.State[CirqNode], node: cirq.CCXPowGate):
        x = state.lower(cirq.XPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Control(x, n_controls=2))

    def visit_CCZPowGate(self, state: lowering.State[CirqNode], node: cirq.CCZPowGate):
        z = state.lower(cirq.ZPowGate(exponent=node.exponent)).expect_one()
        return state.current_frame.push(op.stmts.Control(z, n_controls=2))

    def visit_BitFlipChannel(
        self, state: lowering.State[CirqNode], node: cirq.BitFlipChannel
    ):
        x = state.current_frame.push(op.stmts.X())
        p = state.current_frame.push(py.Constant(node.p))
        return state.current_frame.push(
            noise.stmts.PauliError(basis=x.result, p=p.result)
        )
