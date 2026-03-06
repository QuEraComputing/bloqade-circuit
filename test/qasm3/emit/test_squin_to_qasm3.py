"""Tests for SQUIN -> QASM3 emission path.

Covers:
- SquinQallocToQRegNew rewrite rule (rewrite.py)
- QASM3Emitter.emit() applied to squin-dialect IR (target.py)
- py.constant / py.indexing registered for emit.qasm3.main (expr/_emit.py)
"""

import textwrap
from unittest.mock import MagicMock

from kirin.rewrite import Walk
from kirin.dialects import func

from bloqade import qasm3, squin
from bloqade.qasm3.emit import QASM3Emitter
from bloqade.qasm3.emit.rewrite import SquinQallocToQRegNew
from bloqade.qasm3.dialects.core.stmts import QRegNew
from bloqade.qasm3.dialects.expr.stmts import ConstInt

# ---------------------------------------------------------------------------
# SquinQallocToQRegNew rewrite rule unit tests
# ---------------------------------------------------------------------------


def test_rewrite_no_op_on_non_qalloc_invoke():
    """Rule ignores func.Invoke calls that are not 'qalloc'."""

    @squin.kernel
    def prog():
        q = squin.qalloc(2)
        squin.h(q[0])

    rule = SquinQallocToQRegNew()
    for stmt in prog.callable_region.walk():
        if isinstance(stmt, func.Invoke) and stmt.callee.sym_name != "qalloc":
            result = rule.rewrite_Statement(stmt)
            assert not result.has_done_something


def test_rewrite_replaces_qalloc_invoke_with_qreg_new():
    """SquinQallocToQRegNew replaces func.Invoke(qalloc) with QRegNew."""

    @squin.kernel
    def prog():
        q = squin.qalloc(3)
        squin.h(q[0])

    qalloc_before = [
        s
        for s in prog.callable_region.walk()
        if isinstance(s, func.Invoke) and s.callee.sym_name == "qalloc"
    ]
    assert len(qalloc_before) == 1

    Walk(SquinQallocToQRegNew()).rewrite(prog.code)

    qalloc_after = [
        s
        for s in prog.callable_region.walk()
        if isinstance(s, func.Invoke) and s.callee.sym_name == "qalloc"
    ]
    qreg_news = [s for s in prog.callable_region.walk() if isinstance(s, QRegNew)]
    assert len(qalloc_after) == 0
    assert len(qreg_news) == 1


def test_rewrite_result_has_done_something():
    """RewriteResult.has_done_something is True when qalloc is replaced."""

    @squin.kernel
    def prog():
        q = squin.qalloc(2)  # noqa: F841

    result = Walk(SquinQallocToQRegNew()).rewrite(prog.code)
    assert result.has_done_something


def test_rewrite_no_op_when_no_qalloc():
    """RewriteResult.has_done_something is False when no qalloc is present."""

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)  # noqa: F841

    result = Walk(SquinQallocToQRegNew()).rewrite(prog.code)
    assert not result.has_done_something


# ---------------------------------------------------------------------------
# QASM3Emitter.emit() on squin-dialect IR (end-to-end)
# ---------------------------------------------------------------------------


def test_emit_squin_bell_state():
    """Emitting squin Bell-state IR produces expected QASM3 output."""

    @squin.kernel
    def prog():
        q = squin.qalloc(2)
        squin.h(q[0])
        squin.cx(q[0], q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        qubit[2] q;
        h q[0];
        cx q[0], q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_squin_single_qubit_gates():
    """Single-qubit x/y/z/h gates emit correctly from squin IR."""

    @squin.kernel
    def prog():
        q = squin.qalloc(4)
        squin.x(q[0])
        squin.y(q[1])
        squin.z(q[2])
        squin.h(q[3])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        qubit[4] q;
        x q[0];
        y q[1];
        z q[2];
        h q[3];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_squin_rotation_gates():
    """Rotation gates with float angles emit correctly from squin IR."""

    @squin.kernel
    def prog():
        q = squin.qalloc(2)
        squin.rx(1.5, q[0])
        squin.ry(0.5, q[1])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        qubit[2] q;
        rx(1.5) q[0];
        ry(0.5) q[1];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_squin_ghz_state():
    """GHZ-state preparation emits correct multi-qubit gate sequence."""

    @squin.kernel
    def prog():
        q = squin.qalloc(3)
        squin.h(q[0])
        squin.cx(q[0], q[1])
        squin.cx(q[1], q[2])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        qubit[3] q;
        h q[0];
        cx q[0], q[1];
        cx q[1], q[2];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_squin_larger_register():
    """Emitting squin IR with a larger register preserves register size."""

    @squin.kernel
    def prog():
        q = squin.qalloc(5)
        squin.h(q[0])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";

        qubit[5] q;
        h q[0];
    """)
    assert QASM3Emitter().emit(prog) == expected


def test_emit_squin_include_files_empty():
    """Empty include_files produces no include lines when emitting squin IR."""

    @squin.kernel
    def prog():
        q = squin.qalloc(1)
        squin.h(q[0])

    expected = textwrap.dedent("""\
        OPENQASM 3.0;

        qubit[1] q;
        h q[0];
    """)
    assert QASM3Emitter(include_files=[]).emit(prog) == expected


# ---------------------------------------------------------------------------
# SquinQallocToQRegNew — additional edge cases
# ---------------------------------------------------------------------------


def test_rewrite_non_invoke_no_op():
    """Rewrite rule returns empty result for non-Invoke statements."""
    rule = SquinQallocToQRegNew()
    stmt = ConstInt(value=42)
    result = rule.rewrite_Statement(stmt)
    assert not result.has_done_something


def test_rewrite_invoke_not_qalloc():
    """Rewrite rule returns empty result for non-qalloc Invoke."""
    rule = SquinQallocToQRegNew()

    @qasm3.gate
    def my_gate(q: qasm3.Qubit):
        qasm3.h(q)

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        my_gate(q[0])

    for stmt in prog.callable_region.walk():
        if isinstance(stmt, func.Invoke):
            result = rule.rewrite_Statement(stmt)
            if stmt.callee.sym_name != "qalloc":
                assert not result.has_done_something


def test_rewrite_qalloc_wrong_arg_count():
    """SquinQallocToQRegNew returns no-op for qalloc Invoke with != 1 args."""
    rule = SquinQallocToQRegNew()
    mock_invoke = MagicMock(spec=func.Invoke)
    mock_invoke.__class__ = func.Invoke
    mock_callee = MagicMock()
    mock_callee.sym_name = "qalloc"
    mock_invoke.callee = mock_callee
    mock_invoke.args = ()
    result = rule.rewrite_Statement(mock_invoke)
    assert not result.has_done_something
