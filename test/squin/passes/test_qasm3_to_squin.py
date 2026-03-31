from kirin.passes import TypeInfer
from kirin.rewrite import Walk, Chain
from kirin.dialects import py

import bloqade.squin.rewrite.qasm3 as qasm3_rules
from bloqade import qasm3, squin
from bloqade.rewrite.passes import AggressiveUnroll
from bloqade.squin.passes.qasm3_to_squin import QASM3ToSquin


def test_qasm3_core():
    """Test QRegNew -> qalloc (Invoke), QRegGet -> GetItem, Reset -> reset (Invoke)."""
    from kirin.dialects import func as func_dialect

    from bloqade.qasm3.dialects.core import stmts as core_stmts

    @qasm3.main
    def core_kernel():
        q = qasm3.qreg(5)
        q0 = q[0]
        qasm3.reset(q0)
        return q0

    Walk(
        Chain(
            qasm3_rules.QASM3DirectToSquin(),
            qasm3_rules.QASM3ModifiedToSquin(),
        )
    ).rewrite(core_kernel.code)

    TypeInfer(dialects=squin.kernel)(core_kernel)

    stmts = list(core_kernel.callable_region.walk())

    # QRegGet was rewritten to py.GetItem
    get_item_stmts = [stmt for stmt in stmts if isinstance(stmt, py.GetItem)]
    assert len(get_item_stmts) == 1
    assert get_item_stmts[0].index.owner.value == 0

    # No qasm3 core stmts should remain
    qasm3_core_stmts = [
        stmt
        for stmt in stmts
        if isinstance(stmt, (core_stmts.QRegNew, core_stmts.QRegGet, core_stmts.Reset))
    ]
    assert len(qasm3_core_stmts) == 0

    # QRegNew and Reset were rewritten to func.Invoke calls
    invoke_stmts = [stmt for stmt in stmts if isinstance(stmt, func_dialect.Invoke)]
    assert len(invoke_stmts) == 2


def test_qasm3_non_parametric_gates():
    """Test direct 1:1 gate mappings: x, y, z, h, s, t, cx, cy, cz."""

    @qasm3.main
    def non_parametric():
        q = qasm3.qreg(2)
        qasm3.x(q[0])
        qasm3.y(q[0])
        qasm3.z(q[0])
        qasm3.h(q[0])
        qasm3.s(q[0])
        qasm3.t(q[0])
        qasm3.cx(q[0], q[1])
        qasm3.cy(q[0], q[1])
        qasm3.cz(q[0], q[1])
        return q

    Walk(
        Chain(
            qasm3_rules.QASM3DirectToSquin(),
            qasm3_rules.QASM3ModifiedToSquin(),
        )
    ).rewrite(non_parametric.code)
    AggressiveUnroll(dialects=squin.kernel).fixpoint(non_parametric)

    actual_stmts = [
        stmt
        for stmt in non_parametric.callable_region.walk()
        if isinstance(stmt, squin.gate.stmts.Gate)
    ]
    expected_types = [
        squin.gate.stmts.X,
        squin.gate.stmts.Y,
        squin.gate.stmts.Z,
        squin.gate.stmts.H,
        squin.gate.stmts.S,
        squin.gate.stmts.T,
        squin.gate.stmts.CX,
        squin.gate.stmts.CY,
        squin.gate.stmts.CZ,
    ]
    assert [type(s) for s in actual_stmts] == expected_types


def test_qasm3_parametric_gates():
    """Test rotation gates (rx, ry, rz) and UGate argument reordering."""

    theta_val = 1.0
    phi_val = 2.0
    lam_val = 3.0

    @qasm3.main
    def rotation_gates():
        q = qasm3.qreg(2)
        qasm3.rz(q[0], theta_val)
        qasm3.rx(q[0], theta_val)
        qasm3.ry(q[0], theta_val)
        qasm3.u(q[0], theta_val, phi_val, lam_val)
        return q

    QASM3ToSquin(dialects=rotation_gates.dialects)(rotation_gates)
    AggressiveUnroll(dialects=rotation_gates.dialects).fixpoint(rotation_gates)

    actual_stmts = [
        stmt
        for stmt in rotation_gates.callable_region.walk()
        if isinstance(stmt, squin.gate.stmts.Gate)
    ]

    assert len(actual_stmts) == 4
    assert type(actual_stmts[0]) is squin.gate.stmts.Rz
    assert type(actual_stmts[1]) is squin.gate.stmts.Rx
    assert type(actual_stmts[2]) is squin.gate.stmts.Ry
    assert type(actual_stmts[3]) is squin.gate.stmts.U3


def test_qasm3_to_squin_pass():
    """Test the full QASM3ToSquin pass end-to-end."""

    angle = 1.0

    @qasm3.main
    def program():
        q = qasm3.qreg(3)
        qasm3.h(q[0])
        qasm3.cx(q[0], q[1])
        qasm3.rx(q[2], angle)
        qasm3.u(q[0], angle, angle, angle)
        qasm3.reset(q[2])
        return q

    QASM3ToSquin(dialects=program.dialects)(program)
    AggressiveUnroll(dialects=program.dialects).fixpoint(program)

    actual_stmts = [
        type(stmt)
        for stmt in program.callable_region.walk()
        if isinstance(stmt, (squin.gate.stmts.Gate, squin.qubit.stmts.Reset))
    ]
    expected = [
        squin.gate.stmts.H,
        squin.gate.stmts.CX,
        squin.gate.stmts.Rx,
        squin.gate.stmts.U3,
        squin.qubit.stmts.Reset,
    ]
    assert actual_stmts == expected


def test_qasm3_to_squin_with_custom_gate():
    """QASM3ToSquin converts custom gate bodies to squin via CallGraphPass."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def program():
        q = qasm3.qreg(2)
        bell(q[0], q[1])
        return q

    QASM3ToSquin(dialects=program.dialects)(program)
    program.verify()

    # The gate body should have been converted — no qasm3 gate stmts remain
    from bloqade.qasm3.dialects.uop import stmts as uop_stmts
    from bloqade.qasm3.dialects.expr.stmts import GateFunction

    remaining_qasm3 = [
        stmt
        for stmt in program.callable_region.walk()
        if isinstance(stmt, (uop_stmts.SingleQubitGate, uop_stmts.TwoQubitCtrlGate))
    ]
    assert (
        not remaining_qasm3
    ), f"QASM3 gate stmts remain: {[type(s).__name__ for s in remaining_qasm3]}"

    # GateFunction should have been replaced with func.Function
    remaining_gate_func = [
        stmt for stmt in program.code.walk() if isinstance(stmt, GateFunction)
    ]
    assert not remaining_gate_func, "GateFunction nodes should be converted"


# ---------------------------------------------------------------------------
# QASM3ExprToPy rewrite coverage — math functions and binary ops
# ---------------------------------------------------------------------------


def _load_and_convert(source: str):
    """Parse a QASM3 string and run QASM3ToSquin on it."""
    mt = qasm3.loads(source)
    QASM3ToSquin(dialects=mt.dialects)(mt)
    mt.verify()
    return mt


def test_qasm3_expr_to_py_sin():
    """QASM3ExprToPy rewrites sin() expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(sin(a)) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_cos():
    """QASM3ExprToPy rewrites cos() expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(cos(a)) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_tan():
    """QASM3ExprToPy rewrites tan() expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(tan(a)) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_exp():
    """QASM3ExprToPy rewrites exp() expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(exp(a)) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_sqrt():
    """QASM3ExprToPy rewrites sqrt() expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(sqrt(a)) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_binop_in_gate():
    """QASM3ExprToPy rewrites binary ops (Add, Pow) in gate parameters."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(a + 1.0) q; ry(a ** 2.0) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_const_pi():
    """QASM3ExprToPy rewrites ConstPI in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n' "qubit[1] q;\n" "rx(pi) q[0];\n"
    )


def test_qasm3_expr_to_py_const_bool():
    """QASM3ExprToPy rewrites ConstBool in program."""
    _load_and_convert(
        "OPENQASM 3.0;\n"
        "qubit[1] q;\n"
        "bit[1] c;\n"
        "bool a = true;\n"
        "c[0] = measure q[0];\n"
    )


def test_qasm3_expr_to_py_const_complex():
    """QASM3ExprToPy rewrites ConstComplex (imaginary literal) in gate call."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(a) q; }\n"
        "qubit[1] q;\nmyg(1.5im) q[0];\n"
    )


def test_qasm3_expr_to_py_neg():
    """QASM3ExprToPy rewrites Neg expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(-a) q; }\n"
        "qubit[1] q;\nmyg(0.5) q[0];\n"
    )


def test_qasm3_expr_to_py_mod():
    """QASM3ExprToPy rewrites Mod expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(a % 3.0) q; }\n"
        "qubit[1] q;\nmyg(5.0) q[0];\n"
    )


def test_qasm3_expr_to_py_bitnot():
    """QASM3ExprToPy rewrites BitNot expression in gate parameter."""
    _load_and_convert(
        'OPENQASM 3.0;\ninclude "stdgates.inc";\n'
        "gate myg(a) q { rx(~a) q; }\n"
        "qubit[1] q;\nmyg(3) q[0];\n"
    )
