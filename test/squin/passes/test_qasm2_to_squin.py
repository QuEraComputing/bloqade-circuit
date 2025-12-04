import math

from kirin import types as kirin_types
from kirin.rewrite import Walk
from kirin.dialects import py, func, math as kirin_math
from kirin.dialects.ilist import IListType

from bloqade import qasm2, squin
from bloqade.qasm2 import glob, noise, parallel
from bloqade.types import QubitType
from bloqade.squin.passes import QASM2ToSquin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.analysis.address import AddressAnalysis
from bloqade.squin.rewrite.qasm2 import (
    QASM2ExprToSquin,
)
from bloqade.analysis.address.lattice import AddressReg


def test_expr_rewrite():

    @qasm2.main
    def expr_program():
        # constants
        x = 0  # noqa: F841
        # ConstPI only added from lowering
        y = qasm2.dialects.expr.stmts.ConstPI()  # noqa: F841
        z = -1.75  # noqa: F841
        # binary ops
        a = 1 + 1  # noqa: F841
        b = 2 * 2  # noqa: F841
        c = 3 - 3  # noqa: F841
        d = 4 / 4  # noqa: F841
        e = 5**2  # noqa: F841

        # math
        a = 0.2
        qasm2.sin(a)
        qasm2.cos(a)
        qasm2.tan(a)
        qasm2.exp(a)
        qasm2.ln(a)
        qasm2.sqrt(a)
        return

    expr_program.print()

    Walk(QASM2ExprToSquin()).rewrite(expr_program.code)

    expr_program.print()

    actual_stmt_sequence = list(expr_program.callable_region.walk())

    def is_pi_const(stmt: py.Constant):
        return isinstance(stmt, py.Constant) and math.isclose(stmt.value.data, math.pi)

    assert any(is_pi_const(stmt) for stmt in actual_stmt_sequence)

    assert qasm2.expr.ConstFloat not in actual_stmt_sequence
    assert qasm2.expr.ConstInt not in actual_stmt_sequence
    assert qasm2.expr.ConstPI not in actual_stmt_sequence

    no_const_actual_sequence = [
        type(stmt)
        for stmt in actual_stmt_sequence
        if not isinstance(stmt, (py.Constant, func.ConstantNone, func.Return))
    ]

    expected_stmt_sequence = [
        py.unary.stmts.USub,
        py.binop.Add,
        py.binop.Mult,
        py.binop.Sub,
        py.binop.Div,
        py.binop.Pow,
        kirin_math.stmts.sin,
        kirin_math.stmts.cos,
        kirin_math.stmts.tan,
        kirin_math.stmts.exp,
        kirin_math.stmts.log2,
        kirin_math.stmts.sqrt,
    ]

    assert no_const_actual_sequence == expected_stmt_sequence


def test_qasm2_core():

    @qasm2.main(fold=False)
    def core_kernel():
        q = qasm2.qreg(5)
        q0 = q[0]
        qasm2.reset(q0)
        return q0

    QASM2ToSquin(dialects=squin.kernel)(core_kernel)

    stmts = list(core_kernel.callable_region.walk())
    get_item_stmt = [stmt for stmt in stmts if isinstance(stmt, py.GetItem)]
    assert len(get_item_stmt) == 1
    get_item_stmt = get_item_stmt[0]
    assert get_item_stmt.obj.type == IListType[QubitType, kirin_types.Any]
    idx_const = get_item_stmt.index.owner
    assert idx_const.value.data == 0

    # do aggressive unroll, confirm there are 5 qubit.news()
    AggressiveUnroll(dialects=squin.kernel).fixpoint(core_kernel)

    unrolled_stmts = list(core_kernel.callable_region.walk())
    filtered_stmts = [
        stmt
        for stmt in unrolled_stmts
        if isinstance(stmt, (squin.qubit.stmts.New, squin.qubit.stmts.Reset))
    ]
    expected_stmts = [squin.qubit.stmts.New] * 5 + [squin.qubit.stmts.Reset]

    assert [type(stmt) for stmt in filtered_stmts] == expected_stmts


def test_non_parametric_gates():

    @qasm2.main
    def non_parametric_gates():
        # 1q gates
        q = qasm2.qreg(1)
        qasm2.id(q[0])
        qasm2.x(q[0])
        qasm2.y(q[0])
        qasm2.z(q[0])
        qasm2.h(q[0])
        qasm2.s(q[0])
        qasm2.t(q[0])
        qasm2.sx(q[0])

        # 2q gates
        qasm2.cx(q[0], q[1])
        qasm2.cy(q[0], q[1])
        qasm2.cz(q[0], q[1])

        return q

    non_parametric_gates.print()
    QASM2ToSquin(dialects=squin.kernel)(non_parametric_gates)
    AggressiveUnroll(dialects=squin.kernel).fixpoint(non_parametric_gates)

    actual_stmts = list(non_parametric_gates.callable_region.walk())
    # should be no identity whatsoever
    assert not any(isinstance(stmt, qasm2.uop.stmts.Id) for stmt in actual_stmts)
    actual_stmts = [
        stmt for stmt in actual_stmts if isinstance(stmt, squin.gate.stmts.Gate)
    ]
    expected_stmts = [
        squin.gate.stmts.X,
        squin.gate.stmts.Y,
        squin.gate.stmts.Z,
        squin.gate.stmts.H,
        squin.gate.stmts.S,
        squin.gate.stmts.T,
        squin.gate.stmts.SqrtX,
        squin.gate.stmts.CX,
        squin.gate.stmts.CY,
        squin.gate.stmts.CZ,
    ]

    assert [type(stmt) for stmt in actual_stmts] == expected_stmts


def test_parametric_gates():

    const_pi = math.pi

    @qasm2.main
    def rotation_gates():
        q = qasm2.qreg(3)
        half_turn = const_pi
        quarter_turn = const_pi / 2
        eighth_turn = const_pi / 4
        qasm2.rz(q[0], half_turn)
        qasm2.rx(q[1], half_turn)
        qasm2.ry(q[2], half_turn)

        qasm2.u3(q[0], half_turn, quarter_turn, eighth_turn)
        qasm2.u2(q[0], quarter_turn, half_turn)
        qasm2.u1(q[0], eighth_turn)
        return q

    rotation_gates.print()
    QASM2ToSquin(dialects=squin.kernel)(rotation_gates)
    AggressiveUnroll(dialects=squin.kernel).fixpoint(rotation_gates)
    rotation_gates.print()

    actual_stmts = list(rotation_gates.callable_region.walk())
    actual_stmts = [
        stmt for stmt in actual_stmts if isinstance(stmt, squin.gate.stmts.Gate)
    ]

    assert len(actual_stmts) == 6

    assert type(actual_stmts[0]) is squin.gate.stmts.Rz
    assert actual_stmts[0].angle.owner.value.data == 0.5
    assert type(actual_stmts[1]) is squin.gate.stmts.Rx
    assert actual_stmts[1].angle.owner.value.data == 0.5
    assert type(actual_stmts[2]) is squin.gate.stmts.Ry
    assert actual_stmts[2].angle.owner.value.data == 0.5

    # U3
    assert type(actual_stmts[3]) is squin.gate.stmts.U3
    assert actual_stmts[3].theta.owner.value.data == 0.5
    assert actual_stmts[3].phi.owner.value.data == 0.25
    assert actual_stmts[3].lam.owner.value.data == 0.125

    # U2 is just U3(pi/2, phi, lam)
    assert type(actual_stmts[4]) is squin.gate.stmts.U3
    assert actual_stmts[4].theta.owner.value.data == 0.25
    assert actual_stmts[4].phi.owner.value.data == 0.25
    assert actual_stmts[4].lam.owner.value.data == 0.5

    assert type(actual_stmts[5]) is squin.gate.stmts.U3
    assert actual_stmts[5].theta.owner.value.data == 0.0
    assert actual_stmts[5].phi.owner.value.data == 0.0
    assert actual_stmts[5].lam.owner.value.data == 0.125


def test_noise():

    @qasm2.extended
    def noise_program():
        q = qasm2.qreg(4)
        noise.atom_loss_channel(qargs=q, prob=0.05)
        noise.pauli_channel(qargs=q, px=0.01, py=0.02, pz=0.03)
        noise.cz_pauli_channel(
            ctrls=[q[0], q[1]],
            qargs=[q[2], q[3]],
            px_ctrl=0.01,
            py_ctrl=0.02,
            pz_ctrl=0.03,
            px_qarg=0.04,
            py_qarg=0.05,
            pz_qarg=0.06,
            paired=True,
        )
        return q

    noise_program.print()
    QASM2ToSquin(dialects=noise_program.dialects)(noise_program)
    AggressiveUnroll(dialects=noise_program.dialects).fixpoint(noise_program)
    frame, _ = AddressAnalysis(dialects=noise_program.dialects).run(noise_program)

    actual_stmts = list(noise_program.callable_region.walk())
    actual_stmts = [
        stmt
        for stmt in actual_stmts
        if isinstance(stmt, squin.noise.stmts.NoiseChannel)
    ]

    assert type(actual_stmts[0]) is squin.noise.stmts.QubitLoss
    assert actual_stmts[0].p.owner.value.data == 0.05

    assert type(actual_stmts[1]) is squin.noise.stmts.SingleQubitPauliChannel
    assert actual_stmts[1].px.owner.value.data == 0.01
    assert actual_stmts[1].py.owner.value.data == 0.02
    assert actual_stmts[1].pz.owner.value.data == 0.03

    # originate from the same cz_pauli_channel
    assert type(actual_stmts[2]) is squin.noise.stmts.SingleQubitPauliChannel
    assert type(actual_stmts[3]) is squin.noise.stmts.SingleQubitPauliChannel
    # control qubits
    assert frame.get(actual_stmts[2].qubits) == AddressReg(data=(0, 1))
    # target qubits
    assert frame.get(actual_stmts[3].qubits) == AddressReg(data=(2, 3))
    # assert probabilities are correct on control
    assert actual_stmts[2].px.owner.value.data == 0.01
    assert actual_stmts[2].py.owner.value.data == 0.02
    assert actual_stmts[2].pz.owner.value.data == 0.03
    # assert probabilities are correct on targets
    assert actual_stmts[3].px.owner.value.data == 0.04
    assert actual_stmts[3].py.owner.value.data == 0.05
    assert actual_stmts[3].pz.owner.value.data == 0.06


def test_global_and_parallel():

    const_pi = math.pi

    @qasm2.extended
    def global_parallel_program():
        q = qasm2.qreg(6)
        half_turn = const_pi
        quarter_turn = const_pi / 2
        eighth_turn = const_pi / 4

        parallel.u([q[0]], half_turn, quarter_turn, eighth_turn)
        glob.u([q[2], q[1], q[3]], half_turn, quarter_turn, eighth_turn)
        parallel.rz([q[4], q[5]], eighth_turn)
        return q

    global_parallel_program.print()
    QASM2ToSquin(dialects=global_parallel_program.dialects)(global_parallel_program)
    AggressiveUnroll(dialects=global_parallel_program.dialects).fixpoint(
        global_parallel_program
    )

    actual_stmts = list(global_parallel_program.callable_region.walk())
    actual_stmts = [
        stmt for stmt in actual_stmts if isinstance(stmt, squin.gate.stmts.Gate)
    ]

    assert type(actual_stmts[0]) is squin.gate.stmts.U3
    assert actual_stmts[0].theta.owner.value.data == 0.5
    assert actual_stmts[0].phi.owner.value.data == 0.25
    assert actual_stmts[0].lam.owner.value.data == 0.125

    assert type(actual_stmts[1]) is squin.gate.stmts.U3
    assert actual_stmts[1].theta.owner.value.data == 0.5
    assert actual_stmts[1].phi.owner.value.data == 0.25
    assert actual_stmts[1].lam.owner.value.data == 0.125

    assert type(actual_stmts[2]) is squin.gate.stmts.Rz
    assert actual_stmts[2].angle.owner.value.data == 0.125


def test_func():

    @qasm2.main
    def sub_kernel(ctrl, target):
        qasm2.cx(ctrl, target)
        return

    @qasm2.main
    def main_kernel():
        q = qasm2.qreg(2)
        sub_kernel(q[0], q[1])
        return q

    main_kernel.print()
    QASM2ToSquin(dialects=main_kernel.dialects)(main_kernel)
    AggressiveUnroll(dialects=main_kernel.dialects).fixpoint(main_kernel)
    main_kernel.print()


test_func()
