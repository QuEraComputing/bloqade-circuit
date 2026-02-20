"""Tests for the @qasm3.gate decorator and custom gate emission.

Tests:
- Gate decorator produces correct IR (GateFunction)
- Gate decorator works with all gate types (single, rotation, two-qubit)
- Gates can be called from @qasm3.main programs
- Emitter produces valid QASM3 gate definitions
- Emitter handles parameterized gates
- Multiple custom gates in one program
"""

import textwrap

from bloqade import qasm3
from bloqade.qasm3.emit import QASM3Emitter
from bloqade.qasm3.dialects.expr.stmts import GateFunction


# --- @qasm3.gate decorator IR tests ---


def test_gate_decorator_produces_gate_function():
    """@qasm3.gate wraps the function body in a GateFunction IR node."""

    @qasm3.gate
    def my_gate(q: qasm3.Qubit):
        qasm3.h(q)

    assert isinstance(my_gate.code, GateFunction)


def test_gate_decorator_bell_gate_ir():
    """Bell gate IR contains h and cx operations."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    assert isinstance(bell.code, GateFunction)
    bell.code.verify()


def test_gate_decorator_with_rotation():
    """Gate with a rotation parameter lowers correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, angle: float):
        qasm3.rx(q, angle)

    assert isinstance(rot.code, GateFunction)
    rot.code.verify()


def test_gate_decorator_all_single_qubit_gates():
    """All single-qubit gates can be used inside @qasm3.gate."""

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


def test_gate_decorator_two_qubit_gates():
    """Two-qubit controlled gates work inside @qasm3.gate."""

    @qasm3.gate
    def ctrl_gates(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.cx(a, b)
        qasm3.cy(a, b)
        qasm3.cz(a, b)

    assert isinstance(ctrl_gates.code, GateFunction)
    ctrl_gates.code.verify()


# --- @qasm3.main with gate calls ---


def test_main_calls_gate():
    """A @qasm3.main program can call a @qasm3.gate function."""

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
    """A @qasm3.main program can call multiple different gates."""

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
    """A @qasm3.main program can call a parameterized gate."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, angle: float):
        qasm3.rx(q, angle)
        qasm3.rz(q, angle)

    @qasm3.main
    def prog():
        q = qasm3.qreg(1)
        rot(q[0], 1.57)

    prog.verify()


# --- Emitter tests ---


def test_emit_bell_gate_definition():
    """Emitter produces correct QASM3 with a bell gate definition."""

    @qasm3.gate
    def bell_gate(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        bell_gate(q[0], q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate bell_gate a, b {
          h a;
          cx a, b;
        }

        qubit[2] q;
        bell_gate q[0], q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_parameterized_gate_definition():
    """Emitter separates classical params from qubit args in gate def."""

    @qasm3.gate
    def my_rot(q: qasm3.Qubit, theta: float):
        qasm3.rx(q, theta)

    @qasm3.main
    def prog():
        q = qasm3.qreg(1)
        my_rot(q[0], 1.57)

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate my_rot(theta) q {
          rx(theta) q;
        }

        qubit[1] q;
        my_rot(1.57) q[0];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_multiple_gates():
    """Emitter produces definitions for all custom gates used."""

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

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate prep q {
          h q;
        }

        gate entangle a, b {
          cx a, b;
        }

        qubit[2] q;
        prep q[0];
        entangle q[0], q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_gate_not_duplicated():
    """A gate called multiple times is only defined once."""

    @qasm3.gate
    def my_x(q: qasm3.Qubit):
        qasm3.x(q)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        my_x(q[0])
        my_x(q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate my_x q {
          x q;
        }

        qubit[2] q;
        my_x q[0];
        my_x q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_full_program_with_gate_and_measure():
    """Full program: gate def + calls + measurement emits valid QASM3."""

    @qasm3.gate
    def bell(a: qasm3.Qubit, b: qasm3.Qubit):
        qasm3.h(a)
        qasm3.cx(a, b)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        c = qasm3.bitreg(2)
        bell(q[0], q[1])
        qasm3.measure(q[0], c[0])
        qasm3.measure(q[1], c[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        gate bell a, b {
          h a;
          cx a, b;
        }

        qubit[2] q;
        bit[2] c;
        bell q[0], q[1];
        c[0] = measure q[0];
        c[1] = measure q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected
