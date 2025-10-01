from kirin import ir
from kirin.rewrite import Walk
from kirin.dialects import py

from bloqade.squin.op import stmts as op_stmts
from bloqade.test_utils import assert_nodes
from bloqade.squin.op.rewrite import CanonicalizeAdjointRot


def test_rot_canonicalize():
    angle = ir.TestValue()
    axis = ir.TestValue()
    test_block = ir.Block()
    test_block.stmts.append(rot := op_stmts.Rot(angle=angle, axis=axis))
    test_block.stmts.append(final_op := op_stmts.Adjoint(rot.result))
    test_block.stmts.append(op_stmts.Control(final_op.result, n_controls=1))

    Walk(CanonicalizeAdjointRot()).rewrite(test_block)

    expected_block = ir.Block()
    expected_block.stmts.append(rot := op_stmts.Rot(angle=angle, axis=axis))
    expected_block.stmts.append(new_angle := py.USub(angle))
    expected_block.stmts.append(new_axis := op_stmts.Adjoint(op=axis))
    expected_block.stmts.append(
        final_op := op_stmts.Rot(new_axis.result, new_angle.result)
    )
    expected_block.stmts.append(op_stmts.Control(final_op.result, n_controls=1))

    assert_nodes(test_block, expected_block)
