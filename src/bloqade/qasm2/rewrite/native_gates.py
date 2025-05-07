import math
from typing import List, Optional
from functools import cached_property
from dataclasses import field, dataclass

import cirq
import numpy as np
import cirq.transformers
import cirq.contrib.qasm_import
import cirq.transformers.target_gatesets
import cirq.transformers.target_gatesets.compilation_target_gateset
from kirin import ir
from kirin.rewrite import abc
from kirin.dialects import py
from cirq.circuits.qasm_output import QasmUGate
from cirq.transformers.target_gatesets.compilation_target_gateset import (
    CompilationTargetGateset,
)

from bloqade.qasm2.dialects import uop, expr


# rydeberg gate sets
class RydbergTargetGateset(cirq.CZTargetGateset):
    def __init__(self, *, cnz_max_size: int = 2, atol: float = 1e-8):
        additional = [cirq.Z.controlled(cn) for cn in range(2, cnz_max_size)]
        super().__init__(atol=atol, additional_gates=additional)
        self.cnz_max_size = cnz_max_size

    @property
    def num_qubits(self) -> int:
        return max(2, self.cnz_max_size)


# decompose the CU by defining a custom Cirq Gate with the qelib1 definition
# Need to be careful about the fact that U(theta, phi, lambda) in standard QASM2
# and its variants
class CU(cirq.Gate):
    def __init__(self, theta, phi, lam, gamma):
        super(CU, self)
        self.theta = theta
        self.phi = phi
        self.lam = lam
        self.gamma = gamma

    def _num_qubits_(self):
        return 2

    def _decompose_(self, qubits):
        ctrl, target = qubits
        # taken from qelib1 definition
        # p(gamma) c;
        yield QasmUGate(0, 0, self.gamma / math.pi)(ctrl)
        # p((lambda+phi/2)) c;
        yield QasmUGate(0, 0, ((self.lam + self.phi) / 2) / math.pi)(ctrl)
        # p((lambda-phi/2)) t;
        yield QasmUGate(0, 0, ((self.lam - self.phi) / 2) / math.pi)(target)
        # cx c,t
        yield cirq.CX(ctrl, target)
        # u(-theta/2, 0, -(phi+lambda/2)) t;
        yield QasmUGate(
            (-self.theta / 2) / math.pi, 0, (-(self.phi + self.lam) / 2) / math.pi
        )(target)
        # cx c,t
        yield cirq.CX(ctrl, target)
        # u(theta/2, phi, 0) t;
        yield QasmUGate((self.theta / 2) / math.pi, self.phi / math.pi, 0)(target)

    def _circuit_diagram_info_(self, args):
        return "*", "CU"


def around(val) -> float:
    return float(np.around(val, 14))


def one_qubit_gate_to_u3_angles(op: cirq.Operation) -> tuple[float, float, float]:
    lam, theta, phi = (  # Z angle, Y angle, then Z angle
        cirq.deconstruct_single_qubit_matrix_into_angles(cirq.unitary(op))
    )
    return around(theta), around(phi), around(lam)


@dataclass
class RydbergGateSetRewriteRule(abc.RewriteRule):
    # NOTE
    # 1. this can only rewrite qasm2.main and qasm2.gate!
    dialect_group: ir.DialectGroup
    gateset: CompilationTargetGateset = field(default_factory=RydbergTargetGateset)

    @cached_property
    def cached_qubits(self) -> tuple[cirq.LineQubit, ...]:

        # qasm2 stmts only have up to 3 qubits gates, so we cached only 3.
        return tuple(cirq.LineQubit(i) for i in range(3))

    @cached_property
    def const_float_type(self):
        if expr.dialect in self.dialect_group.data:
            return expr.ConstFloat
        else:
            return py.constant.Constant

    def const_float(self, value: float):
        return self.const_float_type(value=value)

    @cached_property
    def const_pi(self):
        if expr in self.dialect_group.data:
            return expr.ConstPI()
        else:
            return py.constant.Constant(value=math.pi)

    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        # only deal with uop
        if type(node) in uop.dialect.stmts:
            return getattr(self, f"rewrite_{node.name}")(node)

        return abc.RewriteResult()

    def rewrite_barrier(self, node: uop.Barrier) -> abc.RewriteResult:
        return abc.RewriteResult()

    def rewrite_cz(self, node: uop.CZ) -> abc.RewriteResult:
        return abc.RewriteResult()

    def rewrite_CX(self, node: uop.CX) -> abc.RewriteResult:
        return self._rewrite_2q_ctrl_gates(
            cirq.CX(self.cached_qubits[0], self.cached_qubits[1]), node
        )

    def rewrite_cy(self, node: uop.CY) -> abc.RewriteResult:
        return self._rewrite_2q_ctrl_gates(
            cirq.ControlledGate(cirq.Y, 1)(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )

    def rewrite_U(self, node: uop.UGate) -> abc.RewriteResult:
        return abc.RewriteResult()

    def rewrite_id(self, node: uop.Id) -> abc.RewriteResult:
        node.delete()  # just delete the identity gate
        return abc.RewriteResult(has_done_something=True)

    def rewrite_h(self, node: uop.H) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.H(self.cached_qubits[0]), node)

    def rewrite_x(self, node: uop.X) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.X(self.cached_qubits[0]), node)

    def rewrite_y(self, node: uop.Y) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.Y(self.cached_qubits[0]), node)

    def rewrite_z(self, node: uop.Z) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.Z(self.cached_qubits[0]), node)

    def rewrite_s(self, node: uop.S) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.S(self.cached_qubits[0]), node)

    def rewrite_sdg(self, node: uop.Sdag) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.S(self.cached_qubits[0]) ** -1, node)

    def rewrite_t(self, node: uop.T) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.T(self.cached_qubits[0]), node)

    def rewrite_tdg(self, node: uop.Tdag) -> abc.RewriteResult:
        return self._rewrite_1q_gates(cirq.T(self.cached_qubits[0]) ** -1, node)

    def rewrite_sx(self, node: uop.SX) -> abc.RewriteResult:
        return self._rewrite_1q_gates(
            cirq.XPowGate(exponent=0.5).on(self.cached_qubits[0]), node
        )

    def rewrite_ccx(self, node: uop.CCX) -> abc.RewriteResult:
        # from https://algassert.com/quirk#circuit=%7B%22cols%22:%5B%5B%22QFT3%22%5D,%5B%22inputA3%22,1,1,%22+=A3%22%5D,%5B1,1,1,%22%E2%80%A2%22,%22%E2%80%A2%22,%22X%22%5D,%5B1,1,1,%22%E2%80%A6%22,%22%E2%80%A6%22,%22%E2%80%A6%22%5D,%5B1,1,1,1,%22%E2%80%A2%22,%22Z%22%5D,%5B1,1,1,1,1,%22X%5E-%C2%BC%22%5D,%5B1,1,1,%22%E2%80%A2%22,1,%22Z%22%5D,%5B1,1,1,1,1,%22X%5E%C2%BC%22%5D,%5B1,1,1,1,%22%E2%80%A2%22,%22Z%22%5D,%5B1,1,1,1,1,%22X%5E-%C2%BC%22%5D,%5B1,1,1,%22Z%5E%C2%BC%22,%22Z%5E%C2%BC%22%5D,%5B1,1,1,1,%22H%22%5D,%5B1,1,1,%22%E2%80%A2%22,1,%22Z%22%5D,%5B1,1,1,%22%E2%80%A2%22,%22Z%22%5D,%5B1,1,1,1,%22X%5E-%C2%BC%22,%22X%5E%C2%BC%22%5D,%5B1,1,1,%22%E2%80%A2%22,%22Z%22%5D,%5B1,1,1,1,%22H%22%5D%5D%7D

        # x^(1/4)
        lam1, theta1, phi1 = map(
            self.const_float,
            map(around, (1.5707963267948966, 0.7853981633974483, -1.5707963267948966)),
        )
        lam1.insert_before(node)
        theta1.insert_before(node)
        phi1.insert_before(node)

        lam1 = lam1.result
        theta1 = theta1.result
        phi1 = phi1.result

        # x^(-1/4)
        lam2, theta2, phi2 = map(
            self.const_float,
            map(around, (4.71238898038469, 0.7853981633974483, 1.5707963267948966)),
        )
        lam2.insert_before(node)
        theta2.insert_before(node)
        phi2.insert_before(node)
        lam2 = lam2.result
        theta2 = theta2.result
        phi2 = phi2.result

        uop.CZ(ctrl=node.ctrl1, qarg=node.qarg).insert_before(node)
        uop.UGate(node.qarg, theta2, phi2, lam2).insert_before(node)
        uop.CZ(ctrl=node.ctrl2, qarg=node.qarg).insert_before(node)
        uop.UGate(node.qarg, theta1, phi1, lam1).insert_before(node)
        uop.CZ(ctrl=node.ctrl1, qarg=node.qarg).insert_before(node)
        uop.UGate(node.qarg, theta2, phi2, lam2).insert_before(node)
        uop.T(node.ctrl1).insert_before(node)
        uop.T(node.ctrl2).insert_before(node)
        uop.H(node.ctrl1).insert_before(node)
        uop.CZ(ctrl=node.ctrl2, qarg=node.qarg).insert_before(node)
        uop.CZ(ctrl=node.ctrl2, qarg=node.ctrl1).insert_before(node)
        uop.UGate(node.ctrl1, theta2, phi2, lam2).insert_before(node)
        uop.UGate(node.qarg, theta2, phi2, lam2).insert_before(node)
        uop.CZ(ctrl=node.ctrl2, qarg=node.ctrl1).insert_before(node)
        uop.H(node.ctrl1).insert_before(node)
        node.delete()  # delete the original CCX gate

        return abc.RewriteResult(has_done_something=True)

    def rewrite_sxdg(self, node: uop.SXdag) -> abc.RewriteResult:
        return self._rewrite_1q_gates(
            cirq.XPowGate(exponent=-0.5).on(self.cached_qubits[0]), node
        )

    def rewrite_u1(self, node: uop.U1) -> abc.RewriteResult:
        theta = node.lam
        (phi := self.const_float(value=0.0)).insert_before(node)
        node.replace_by(
            uop.UGate(qarg=node.qarg, theta=phi.result, phi=phi.result, lam=theta)
        )
        return abc.RewriteResult(has_done_something=True)

    def rewrite_u2(self, node: uop.U2) -> abc.RewriteResult:
        phi = node.phi
        lam = node.lam
        (theta := self.const_float(value=math.pi / 2)).insert_before(node)
        node.replace_by(uop.UGate(qarg=node.qarg, theta=theta.result, phi=phi, lam=lam))
        return abc.RewriteResult(has_done_something=True)

    def rewrite_rx(self, node: uop.RX) -> abc.RewriteResult:
        theta = node.theta
        (phi := self.const_float(value=math.pi / 2)).insert_before(node)
        (lam := self.const_float(value=-math.pi / 2)).insert_before(node)
        node.replace_by(
            uop.UGate(qarg=node.qarg, theta=theta, phi=phi.result, lam=lam.result)
        )
        return abc.RewriteResult(has_done_something=True)

    def rewrite_ry(self, node: uop.RY) -> abc.RewriteResult:
        theta = node.theta
        (phi := self.const_float(value=0.0)).insert_before(node)
        node.replace_by(
            uop.UGate(qarg=node.qarg, theta=theta, phi=phi.result, lam=phi.result)
        )
        return abc.RewriteResult(has_done_something=True)

    def rewrite_rz(self, node: uop.RZ) -> abc.RewriteResult:
        theta = node.theta
        (phi := self.const_float(value=0.0)).insert_before(node)
        node.replace_by(
            uop.UGate(qarg=node.qarg, theta=phi.result, phi=phi.result, lam=theta)
        )
        return abc.RewriteResult(has_done_something=True)

    def rewrite_crx(self, node: uop.CRX) -> abc.RewriteResult:
        lam = self._get_const_value(node.lam)

        if lam is None:
            return abc.RewriteResult()

        return self._rewrite_2q_ctrl_gates(
            cirq.ControlledGate(cirq.Rx(rads=lam), 1).on(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )

    def rewrite_cry(self, node: uop.CRY) -> abc.RewriteResult:
        lam = self._get_const_value(node.lam)

        if lam is None:
            return abc.RewriteResult()

        return self._rewrite_2q_ctrl_gates(
            cirq.ControlledGate(cirq.Ry(rads=lam), 1).on(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )

    def rewrite_crz(self, node: uop.CRZ) -> abc.RewriteResult:
        lam = self._get_const_value(node.lam)

        if lam is None:
            return abc.RewriteResult()

        return self._rewrite_2q_ctrl_gates(
            cirq.ControlledGate(cirq.Rz(rads=lam), 1).on(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )

    def rewrite_cu1(self, node: uop.CU1) -> abc.RewriteResult:

        lam = self._get_const_value(node.lam)

        if lam is None:
            return abc.RewriteResult()

        # cirq.ControlledGate(u3(0, 0, lambda))
        return self._rewrite_2q_ctrl_gates(
            cirq.ControlledGate(QasmUGate(0, 0, lam / math.pi)).on(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )
        pass

    def rewrite_cu3(self, node: uop.CU3) -> abc.RewriteResult:

        theta = self._get_const_value(node.theta)
        lam = self._get_const_value(node.lam)
        phi = self._get_const_value(node.phi)
        if theta is None or lam is None or phi is None:
            return abc.RewriteResult()

        # cirq.ControlledGate(u3(theta, lambda phi))
        return self._rewrite_2q_ctrl_gates(
            cirq.ControlledGate(
                QasmUGate(theta / math.pi, phi / math.pi, lam / math.pi)
            ).on(self.cached_qubits[0], self.cached_qubits[1]),
            node,
        )

    def rewrite_cu(self, node: uop.CU) -> abc.RewriteResult:

        gamma = self._get_const_value(node.gamma)
        theta = self._get_const_value(node.theta)
        lam = self._get_const_value(node.lam)
        phi = self._get_const_value(node.phi)

        # need to create custom 2q gate, then feed that into rewrite_2q

        return self._rewrite_2q_ctrl_gates(
            CU(theta, phi, lam, gamma).on(self.cached_qubits[0], self.cached_qubits[1]),
            node,
        )

    def rewrite_rxx(self, node: uop.RXX) -> abc.RewriteResult:

        theta = self._get_const_value(node.theta)

        if theta is None:
            return abc.RewriteResult()

        # even though the XX gate is not controlled,
        # the end U + CZ decomposition that happens internally means
        return self._rewrite_2q_ctrl_gates(
            cirq.XXPowGate(exponent=theta / math.pi).on(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )

    def rewrite_rzz(self, node: uop.RZZ) -> abc.RewriteResult:
        theta = self._get_const_value(node.theta)

        if theta is None:
            return abc.RewriteResult()

        return self._rewrite_2q_ctrl_gates(
            cirq.ZZPowGate(exponent=theta / math.pi).on(
                self.cached_qubits[0], self.cached_qubits[1]
            ),
            node,
        )

        """
        return self._rewrite_2q_ctrl_gates(
            cirq.ZZPowGate(exponent = theta).on(self.cached_qubits[0], self.cached_qubits[1])
            ,node
        )
        """

    def rewrite_swap(self, node: uop.Swap):
        return self._rewrite_2q_ctrl_gates(
            cirq.SWAP(self.cached_qubits[0], self.cached_qubits[1]), node
        )

    def _get_const_value(self, ssa: ir.SSAValue) -> Optional[float | int]:
        if not isinstance(ssa, ir.ResultValue):
            return None

        match ssa.owner:
            case expr.ConstFloat(value=value):
                return value
            case expr.ConstInt(value=value):
                return value
            case py.constant.Constant(value=float() as value) | py.constant.Constant(
                value=int() as value
            ):
                return value
            case expr.ConstPI():
                return math.pi
            case _:
                return None

    def _generate_1q_gate_stmts(self, cirq_gate: cirq.Operation, qarg: ir.SSAValue):
        target_gates = self.gateset.decompose_to_target_gateset(cirq_gate, 0)

        if isinstance(target_gates, cirq.GateOperation):
            target_gates = [target_gates]

        new_stmts = []
        for new_gate in target_gates:
            theta, phi, lam = one_qubit_gate_to_u3_angles(new_gate)
            theta_stmt = self.const_float(value=theta)
            phi_stmt = self.const_float(value=phi)
            lam_stmt = self.const_float(value=lam)

            new_stmts.append(theta_stmt)
            new_stmts.append(phi_stmt)
            new_stmts.append(lam_stmt)
            new_stmts.append(
                uop.UGate(
                    qarg=qarg,
                    theta=theta_stmt.result,
                    phi=phi_stmt.result,
                    lam=lam_stmt.result,
                )
            )
        return new_stmts

    def _rewrite_1q_gates(
        self, cirq_gate: cirq.Operation, node: uop.SingleQubitGate
    ) -> abc.RewriteResult:
        new_gate_stmts = self._generate_1q_gate_stmts(cirq_gate, node.qarg)
        return self._rewrite_gate_stmts(new_gate_stmts, node)

    def _generate_multi_ctrl_gate_stmts(
        self, cirq_gate: cirq.Operation, qubits_ssa: List[ir.SSAValue]
    ) -> list[ir.Statement]:
        qubit_to_ssa_map = {
            q: ssa for q, ssa in zip(self.cached_qubits[: len(qubits_ssa)], qubits_ssa)
        }
        target_gates = self.gateset.decompose_to_target_gateset(cirq_gate, 0)
        new_stmts = []
        for new_gate in target_gates:
            if len(new_gate.qubits) == 1:
                # 1q
                phi0, phi1, phi2 = one_qubit_gate_to_u3_angles(new_gate)
                phi0_stmt = self.const_float(value=phi0)
                phi1_stmt = self.const_float(value=phi1)
                phi2_stmt = self.const_float(value=phi2)

                new_stmts.append(phi0_stmt)
                new_stmts.append(phi1_stmt)
                new_stmts.append(phi2_stmt)
                new_stmts.append(
                    uop.UGate(
                        qarg=qubit_to_ssa_map[new_gate.qubits[0]],
                        theta=phi0_stmt.result,
                        phi=phi1_stmt.result,
                        lam=phi2_stmt.result,
                    )
                )
            else:
                # 2q
                new_stmts.append(
                    uop.CZ(
                        ctrl=qubit_to_ssa_map[new_gate.qubits[0]],
                        qarg=qubit_to_ssa_map[new_gate.qubits[1]],
                    )
                )

        return new_stmts

    def _rewrite_2q_ctrl_gates(
        self, cirq_gate: cirq.Operation, node: uop.TwoQubitCtrlGate
    ) -> abc.RewriteResult:
        new_gate_stmts = self._generate_multi_ctrl_gate_stmts(
            cirq_gate, [node.ctrl, node.qarg]
        )
        return self._rewrite_gate_stmts(new_gate_stmts, node)

    def _rewrite_3q_ctrl_gates(
        self, cirq_gate: cirq.Operation, node: uop.CCX
    ) -> abc.RewriteResult:
        new_gate_stmts = self._generate_multi_ctrl_gate_stmts(
            cirq_gate, [node.ctrl1, node.ctrl2, node.qarg]
        )
        return self._rewrite_gate_stmts(new_gate_stmts, node)

    def _rewrite_gate_stmts(
        self, new_gate_stmts: list[ir.Statement], node: ir.Statement
    ):

        node.replace_by(new_gate_stmts[0])
        node = new_gate_stmts[0]

        for stmt in new_gate_stmts[1:]:
            stmt.insert_after(node)
            node = stmt

        return abc.RewriteResult(has_done_something=True)
