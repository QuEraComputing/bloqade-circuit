"""Tests for @qasm3.gate and @qasm3.main decorator lowering."""

from bloqade import qasm3
from bloqade.qasm3.dialects.expr.stmts import GateFunction


# ---------------------------------------------------------------------------
# @qasm3.gate IR
# ---------------------------------------------------------------------------


def test_gate_produces_gate_function():
    """@qasm3.gate wraps the function body in a GateFunction IR node."""

    @qasm3.gate
    def my_gate(q: qasm3.Qubit):
        qasm3.h(q)

    assert isinstance(my_gate.code, GateFunction)


def test_gate_bell():
    """Bell gate IR contains h and cx, verifies cleanly."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    assert isinstance(bell.code, GateFunction)
    bell.code.verify()


def test_gate_with_rotation():
    """Gate with a rotation parameter lowers correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, angle: float):
        qasm3.rx(q, angle)

    assert isinstance(rot.code, GateFunction)
    rot.code.verify()


def test_gate_all_single_qubit():
    """All single-qubit gates work inside @qasm3.gate."""

    @qasm3.gate
    def all_single(q: qasm3.Qubit):
        qasm3.h(q)
        qasm3.x(q)
        qasm3.y(q)
        qasm3.z(q)
        qasm3.s(q)
        qasm3.t(q)

    assert isinstance(all_single.code, GateFunction)
    all_single.code.verify()


def test_gate_two_qubit():
    """Two-qubit controlled gates work inside @qasm3.gate."""

    @qasm3.gate
    def ctrl_gates(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.cx(a, b)
        qasm3.cy(a, b)
        qasm3.cz(a, b)

    assert isinstance(ctrl_gates.code, GateFunction)
    ctrl_gates.code.verify()


# ---------------------------------------------------------------------------
# @qasm3.main calling gates
# ---------------------------------------------------------------------------


def test_main_calls_gate():
    """@qasm3.main can call a @qasm3.gate function."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        bell(q[0], q[1])

    prog.verify()


def test_main_calls_multiple_gates():
    """@qasm3.main can call multiple different gates."""

    @qasm3.gate
    def prep(q: qasm3.Qubit):
        qasm3.h(q)

    @qasm3.gate
    def entangle(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        prep(q[0])
        entangle(q[0], q[1])

    prog.verify()


def test_main_calls_parameterized_gate():
    """@qasm3.main can call a parameterized gate."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, angle: float):
        qasm3.rx(q, angle)
        qasm3.rz(q, angle)

    @qasm3.main
    def prog():
        q = qasm3.qreg(1)
        rot(q[0], 1.57)

    prog.verify()


def test_main_with_builtin_gates_and_custom_gate():
    """@qasm3.main can mix built-in gates, custom gates, and measurements."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        c = qasm3.bitreg(2)
        qasm3.h(q[1])
        bell(q[0], q[1])
        qasm3.measure(q[0], c[0])
        qasm3.measure(q[1], c[1])

    prog.verify()
