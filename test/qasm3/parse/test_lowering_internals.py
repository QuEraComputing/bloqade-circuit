"""Tests for QASM3Lowering internal methods and error paths.

These tests call lowering methods directly to exercise error paths
that are unreachable through normal QASM3 string parsing.
"""

import textwrap
from unittest.mock import PropertyMock, patch

import pytest
import openqasm3.ast as oq3_ast
from kirin import ir, lowering
from openqasm3.parser import parse as oq3_parse

from bloqade.qasm3.groups import main
from bloqade.qasm3.parse.lowering import QASM3Lowering

# ---------------------------------------------------------------------------
# run() method
# ---------------------------------------------------------------------------


def test_lowering_run_method():
    """QASM3Lowering.run() returns an ir.Region."""
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\nh q[0];\n")
    lowerer = QASM3Lowering(main)
    region = lowerer.run(ast)
    assert isinstance(region, ir.Region)


# ---------------------------------------------------------------------------
# visit() — unknown AST node
# ---------------------------------------------------------------------------


def test_lowering_unknown_ast_node():
    """visit() raises BuildError for unknown AST node types."""
    lowerer = QASM3Lowering(main)
    state = lowering.State(lowerer)
    node = oq3_ast.IODeclaration(
        io_identifier=oq3_ast.IOKeyword.input,
        type=oq3_ast.IntType(size=oq3_ast.IntegerLiteral(value=32)),
        identifier=oq3_ast.Identifier(name="x"),
    )
    with pytest.raises(lowering.BuildError, match="Unsupported QASM3 construct"):
        lowerer.visit(state, node)


# ---------------------------------------------------------------------------
# lower_global()
# ---------------------------------------------------------------------------


def test_lowering_global_variable_error():
    """lower_global raises BuildError for non-Identifier globals."""
    lowerer = QASM3Lowering(main)
    state = lowering.State(lowerer)
    node = oq3_ast.IntegerLiteral(value=42)
    with pytest.raises(lowering.BuildError, match="Global variables are not supported"):
        lowerer.lower_global(state, node)


def test_lowering_global_identifier_not_found():
    """lower_global raises BuildError when identifier not in globals."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        node = oq3_ast.Identifier(name="nonexistent_global")
        with pytest.raises(
            lowering.BuildError, match="Global variables are not supported"
        ):
            lowerer.lower_global(state, node)


# ---------------------------------------------------------------------------
# lower_literal() — unsupported type
# ---------------------------------------------------------------------------


def test_lowering_literal_unsupported_type():
    """lower_literal raises BuildError for non-int/float types."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        with pytest.raises(lowering.BuildError, match="Expected value of type"):
            lowerer.lower_literal(state, "string_value")


# ---------------------------------------------------------------------------
# _lower_expression() — unsupported expression type
# ---------------------------------------------------------------------------


def test_lowering_unsupported_expression_type():
    """_lower_expression raises BuildError for unsupported expression types."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        node = oq3_ast.FunctionCall(
            name=oq3_ast.Identifier(name="sin"),
            arguments=[oq3_ast.FloatLiteral(value=1.0)],
        )
        with pytest.raises(lowering.BuildError, match="Unsupported expression type"):
            lowerer._lower_expression(state, node)


# ---------------------------------------------------------------------------
# _lower_binary_expression() — unsupported operator
# ---------------------------------------------------------------------------


def test_lowering_unsupported_binary_operator():
    """_lower_binary_expression raises BuildError for unsupported operators."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        node = oq3_ast.BinaryExpression(
            op=oq3_ast.BinaryOperator["%"],
            lhs=oq3_ast.IntegerLiteral(value=1),
            rhs=oq3_ast.IntegerLiteral(value=2),
        )
        with pytest.raises(lowering.BuildError, match="Unsupported binary operator"):
            lowerer._lower_binary_expression(state, node)


# ---------------------------------------------------------------------------
# _lower_unary_expression() — unsupported operator
# ---------------------------------------------------------------------------


def test_lowering_unsupported_unary_operator():
    """_lower_unary_expression raises BuildError for unsupported operators."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        node = oq3_ast.UnaryExpression(
            op=oq3_ast.UnaryOperator["~"],
            expression=oq3_ast.IntegerLiteral(value=1),
        )
        with pytest.raises(lowering.BuildError, match="Unsupported unary operator"):
            lowerer._lower_unary_expression(state, node)


# ---------------------------------------------------------------------------
# _lower_qubit_ref() error paths
# ---------------------------------------------------------------------------


def test_lowering_complex_qubit_indexing():
    """_lower_qubit_ref raises BuildError for multi-dimensional indexing."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[2] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IndexedIdentifier(
            name=oq3_ast.Identifier(name="q"),
            indices=[
                [oq3_ast.IntegerLiteral(value=0)],
                [oq3_ast.IntegerLiteral(value=1)],
            ],
        )
        with pytest.raises(lowering.BuildError, match="Only simple integer indexing"):
            lowerer._lower_qubit_ref(state, ref)


def test_lowering_non_qreg_qubit_ref():
    """_lower_qubit_ref raises BuildError when register is not a QReg."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nbit[2] c;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IndexedIdentifier(
            name=oq3_ast.Identifier(name="c"),
            indices=[[oq3_ast.IntegerLiteral(value=0)]],
        )
        with pytest.raises(lowering.BuildError, match="Expected quantum register"):
            lowerer._lower_qubit_ref(state, ref)


def test_lowering_undefined_qubit_plain_identifier():
    """_lower_qubit_ref raises BuildError for undefined plain identifier."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.Identifier(name="nonexistent")
        with pytest.raises(lowering.BuildError, match="Undefined qubit"):
            lowerer._lower_qubit_ref(state, ref)


def test_lowering_unsupported_qubit_ref_type():
    """_lower_qubit_ref raises BuildError for unsupported ref types."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IntegerLiteral(value=0)
        with pytest.raises(lowering.BuildError, match="Unsupported qubit reference"):
            lowerer._lower_qubit_ref(state, ref)


# ---------------------------------------------------------------------------
# _lower_bit_ref() error paths
# ---------------------------------------------------------------------------


def test_lowering_complex_bit_indexing():
    """_lower_bit_ref raises BuildError for multi-dimensional indexing."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nbit[2] c;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IndexedIdentifier(
            name=oq3_ast.Identifier(name="c"),
            indices=[
                [oq3_ast.IntegerLiteral(value=0)],
                [oq3_ast.IntegerLiteral(value=1)],
            ],
        )
        with pytest.raises(lowering.BuildError, match="Only simple integer indexing"):
            lowerer._lower_bit_ref(state, ref)


def test_lowering_non_bitreg_bit_ref():
    """_lower_bit_ref raises BuildError when register is not a BitReg."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[2] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IndexedIdentifier(
            name=oq3_ast.Identifier(name="q"),
            indices=[[oq3_ast.IntegerLiteral(value=0)]],
        )
        with pytest.raises(lowering.BuildError, match="Expected bit register"):
            lowerer._lower_bit_ref(state, ref)


def test_lowering_undefined_bit_plain_identifier():
    """_lower_bit_ref raises BuildError for undefined plain identifier."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.Identifier(name="nonexistent")
        with pytest.raises(lowering.BuildError, match="Undefined bit"):
            lowerer._lower_bit_ref(state, ref)


def test_lowering_unsupported_bit_ref_type():
    """_lower_bit_ref raises BuildError for unsupported ref types."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IntegerLiteral(value=0)
        with pytest.raises(lowering.BuildError, match="Unsupported bit reference"):
            lowerer._lower_bit_ref(state, ref)


def test_lowering_undefined_bit_register_indexed():
    """_lower_bit_ref raises BuildError for undefined indexed register."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse("OPENQASM 3.0;\nqubit[1] q;\n")
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False):
        lowerer.visit(state, ast)
        ref = oq3_ast.IndexedIdentifier(
            name=oq3_ast.Identifier(name="nonexistent"),
            indices=[[oq3_ast.IntegerLiteral(value=0)]],
        )
        with pytest.raises(lowering.BuildError, match="Undefined register"):
            lowerer._lower_bit_ref(state, ref)


# ---------------------------------------------------------------------------
# visit_QuantumGate — unknown return type for user-defined gate
# ---------------------------------------------------------------------------


def test_lowering_gate_unknown_return_type():
    """visit_QuantumGate raises BuildError for unknown return type."""
    lowerer = QASM3Lowering(main)
    ast = oq3_parse(textwrap.dedent("""\
        OPENQASM 3.0;
        include "stdgates.inc";
        gate myg q {
            h q;
        }
        qubit[1] q;
        myg q[0];
    """))
    state = lowering.State(lowerer)
    with state.frame([ast], finalize_next=False) as frame:
        for stmt in ast.statements[:-1]:
            lowerer.visit(state, stmt)

        gate_method = frame.globals["myg"]
        with patch.object(
            type(gate_method),
            "return_type",
            new_callable=PropertyMock,
            return_value=None,
        ):
            gate_call = ast.statements[-1]
            with pytest.raises(lowering.BuildError, match="Unknown return type"):
                lowerer.visit(state, gate_call)
