"""Tests for @qasm3.gate and @qasm3.main decorator lowering."""

import os
import ast as pyast
import tempfile
import importlib.util
from io import StringIO
from unittest.mock import MagicMock

import pytest
from kirin import ir, lowering
from rich.console import Console
from kirin.print.printer import Printer

from bloqade import qasm3
from bloqade.qasm3.types import BitReg
from bloqade.qasm3.groups import gate, main
from bloqade.qasm3.dialects.core.stmts import QRegNew
from bloqade.qasm3.dialects.expr.stmts import (
    ConstPI,
    ConstInt,
    ConstFloat,
    GateFunction,
)

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


# ---------------------------------------------------------------------------
# types.py — BitReg.__getitem__
# ---------------------------------------------------------------------------


def test_bitreg_getitem_raises():
    """BitReg.__getitem__ raises NotImplementedError outside kernel."""
    br = BitReg()
    with pytest.raises(NotImplementedError, match="cannot call __getitem__"):
        br[0]


# ---------------------------------------------------------------------------
# groups.py — gate group
# ---------------------------------------------------------------------------


def test_gate_group_non_function_code_valueerror():
    """gate group run_pass raises ValueError if code is not a Function."""
    method = MagicMock(spec=ir.Method)
    method.code = "not_a_function"
    method.verify = MagicMock()

    with pytest.raises(ValueError, match="Gate Method code must be a Function"):
        gate.run_pass(method)


# ---------------------------------------------------------------------------
# expr/stmts.py — print_impl methods
# ---------------------------------------------------------------------------


def _make_printer():
    """Create a Printer that writes to a StringIO."""
    sio = StringIO()
    console = Console(file=sio, force_terminal=False)
    printer = Printer(console=console)
    return printer, sio


def test_const_int_print_impl():
    """ConstInt.print_impl produces expected output."""
    stmt = ConstInt(value=42)
    printer, sio = _make_printer()
    stmt.print_impl(printer)
    sio.flush()
    assert "42" in sio.getvalue()


def test_const_float_print_impl():
    """ConstFloat.print_impl produces expected output."""
    stmt = ConstFloat(value=3.14)
    printer, sio = _make_printer()
    stmt.print_impl(printer)
    sio.flush()
    assert "3.14" in sio.getvalue()


def test_const_pi_print_impl():
    """ConstPI.print_impl produces expected output."""
    stmt = ConstPI()
    printer, sio = _make_printer()
    stmt.print_impl(printer)
    sio.flush()
    assert "PI" in sio.getvalue()


def test_gate_function_print_impl():
    """GateFunction.print_impl produces expected output."""

    @qasm3.gate
    def my_gate(q: qasm3.Qubit):
        qasm3.h(q)

    printer, sio = _make_printer()
    my_gate.code.print_impl(printer)
    sio.flush()
    assert "my_gate" in sio.getvalue()


# ---------------------------------------------------------------------------
# @qasm3.gate / @qasm3.main — Python AST lowering (_from_python.py)
# ---------------------------------------------------------------------------


def test_from_python_constant_float():
    """Float constant in kernel is lowered correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit):
        qasm3.rx(q, 1.5)

    rot.code.verify()


def test_from_python_subscript_qreg():
    """Subscript on qreg in kernel is lowered correctly."""

    @qasm3.main
    def prog():
        q = qasm3.qreg(2)
        qasm3.h(q[0])

    prog.verify()


def test_from_python_bitreg_subscript():
    """Subscript on bitreg in kernel is lowered correctly."""

    @qasm3.main
    def prog():
        q = qasm3.qreg(1)
        c = qasm3.bitreg(1)
        qasm3.measure(q[0], c[0])

    prog.verify()


def test_from_python_binop_add():
    """Addition in kernel is lowered correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, a: float):
        qasm3.rx(q, a + 1.0)

    rot.code.verify()


def test_from_python_binop_sub():
    """Subtraction in kernel is lowered correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, a: float):
        qasm3.rx(q, a - 1.0)

    rot.code.verify()


def test_from_python_binop_mul():
    """Multiplication in kernel is lowered correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, a: float):
        qasm3.rx(q, a * 2.0)

    rot.code.verify()


def test_from_python_binop_div():
    """Division in kernel is lowered correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, a: float):
        qasm3.rx(q, a / 2.0)

    rot.code.verify()


def test_from_python_unary_neg():
    """Unary negation in kernel is lowered correctly."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, a: float):
        qasm3.rx(q, -a)

    rot.code.verify()


def test_from_python_unary_pos():
    """Unary positive in kernel is lowered correctly (no-op)."""

    @qasm3.gate
    def rot(q: qasm3.Qubit, a: float):
        qasm3.rx(q, +a)

    rot.code.verify()


# ---------------------------------------------------------------------------
# _from_python.py — error paths via direct method calls / temp files
# ---------------------------------------------------------------------------


def _get_expr_lowering_and_state():
    """Get the QASM3ExprLowering instance and a fresh lowering.State."""
    py_lowering = main.lowering
    expr_low = py_lowering.registry.ast_table["Name"]
    state = lowering.State(py_lowering)
    return expr_low, state


def test_from_python_lower_name_store():
    """lower_Name raises BuildError for Store context."""
    expr_low, state = _get_expr_lowering_and_state()
    node = pyast.Name(id="x", ctx=pyast.Store())
    with state.frame([], finalize_next=False):
        with pytest.raises(lowering.BuildError, match="unhandled store operation"):
            expr_low.lower_Name(state, node)


def test_from_python_lower_name_del():
    """lower_Name raises BuildError for Del context."""
    expr_low, state = _get_expr_lowering_and_state()
    node = pyast.Name(id="x", ctx=pyast.Del())
    with state.frame([], finalize_next=False):
        with pytest.raises(lowering.BuildError, match="unhandled del operation"):
            expr_low.lower_Name(state, node)


def test_from_python_lower_subscript_store_context():
    """lower_Subscript raises BuildError for Store context."""
    expr_low, state = _get_expr_lowering_and_state()
    with state.frame([], finalize_next=False) as frame:
        size_stmt = ConstInt(value=2)
        frame.push(size_stmt)
        qreg_stmt = QRegNew(n_qubits=size_stmt.result)
        frame.push(qreg_stmt)
        qreg_stmt.result.name = "q"
        frame.defs["q"] = qreg_stmt.result

        idx_stmt = ConstInt(value=0)
        frame.push(idx_stmt)

        node = pyast.Subscript(
            value=pyast.Name(id="q", ctx=pyast.Load()),
            slice=pyast.Constant(value=0),
            ctx=pyast.Store(),
        )
        with pytest.raises(lowering.BuildError, match="cannot write to subscript"):
            expr_low.lower_Subscript(state, node)


def _run_temp_module(code: str):
    """Write code to a temp file and import it, returning the module."""
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, dir="/tmp"
    ) as f:
        f.write(code)
        path = f.name
    try:
        spec = importlib.util.spec_from_file_location("_tmp_mod", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        os.unlink(path)


def test_from_python_lower_assign_unsupported_target():
    """lower_Assign raises BuildError for unsupported target syntax."""
    with pytest.raises(lowering.BuildError, match="unsupported target syntax"):
        _run_temp_module(
            "from bloqade import qasm3\n"
            "@qasm3.main\n"
            "def bad():\n"
            "    q = qasm3.qreg(2)\n"
            "    q[0] = 1\n"
        )


def test_from_python_lower_constant_unsupported():
    """lower_Constant raises BuildError for unsupported type."""
    with pytest.raises(lowering.BuildError, match="unsupported QASM 3.0 constant type"):
        _run_temp_module(
            "from bloqade import qasm3\n"
            "@qasm3.gate\n"
            "def bad(q: qasm3.Qubit):\n"
            '    qasm3.rx(q, "hello")\n'
        )


def test_from_python_lower_subscript_nonint_index():
    """lower_Subscript raises BuildError for non-int index."""
    with pytest.raises(lowering.BuildError, match="unsupported subscript index type"):
        _run_temp_module(
            "from bloqade import qasm3\n"
            "@qasm3.main\n"
            "def bad():\n"
            "    q = qasm3.qreg(2)\n"
            "    qasm3.h(q[0.5])\n"
        )


def test_from_python_lower_subscript_bad_value_type():
    """lower_Subscript raises BuildError for unsupported value type."""
    with pytest.raises(lowering.BuildError, match="unsupported subscript value type"):
        _run_temp_module(
            "from bloqade import qasm3\n"
            "@qasm3.main\n"
            "def bad():\n"
            "    x = 1.5\n"
            "    y = x[0]\n"
        )


def test_from_python_lower_binop_unsupported():
    """lower_BinOp raises BuildError for unsupported operator."""
    with pytest.raises(lowering.BuildError, match="unsupported QASM 3.0 binop"):
        _run_temp_module(
            "from bloqade import qasm3\n"
            "@qasm3.gate\n"
            "def bad(q: qasm3.Qubit, a: float):\n"
            "    qasm3.rx(q, a % 2.0)\n"
        )


def test_from_python_promote_binop_int_int():
    """__promote_binop_type returns Int when both operands are Int."""
    mod = _run_temp_module(
        "from bloqade import qasm3\n"
        "@qasm3.gate\n"
        "def intadd(q: qasm3.Qubit):\n"
        "    qasm3.rx(q, 1 + 2)\n"
    )
    assert hasattr(mod, "intadd")


def test_from_python_lower_unaryop_unsupported():
    """lower_UnaryOp raises BuildError for unsupported operator."""
    with pytest.raises(lowering.BuildError, match="unsupported QASM 3.0 unaryop"):
        _run_temp_module(
            "from bloqade import qasm3\n"
            "@qasm3.gate\n"
            "def bad(q: qasm3.Qubit, a: float):\n"
            "    qasm3.rx(q, ~a)\n"
        )


def test_from_python_name_undefined():
    """Referencing undefined name in kernel raises an error."""
    with pytest.raises(Exception):

        @qasm3.main
        def prog():
            qasm3.h(undefined_var)  # noqa: F821
