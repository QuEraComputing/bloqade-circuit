from kirin import ir
from kirin.rewrite import Walk
from kirin.dialects import py

from bloqade.squin.op import stmts as op_stmts
from bloqade.test_utils import assert_nodes
from bloqade.squin.op.rewrite import CanonicalizeAdjointRot


def test_rot_canonicalize():
    angle = ir.TestValue()
    test_block = ir.Block()
    test_block.stmts.append(axis := op_stmts.X())
    test_block.stmts.append(rot := op_stmts.Rot(angle=angle, axis=axis.result))
    test_block.stmts.append(op_stmts.Adjoint(op=rot.result))

    Walk(CanonicalizeAdjointRot()).rewrite(test_block)

    expected_block = ir.Block()
    expected_block.stmts.append(axis := op_stmts.X())
    expected_block.stmts.append(rot := op_stmts.Rot(angle=angle, axis=axis.result))
    expected_block.stmts.append(new_angle := py.USub(angle))
    expected_block.stmts.append(new_axis := op_stmts.Adjoint(op=axis.result))
    expected_block.stmts.append(
        op_stmts.Rot(angle=new_angle.result, axis=new_axis.result)
    )

    test_block.print()
    expected_block.print()
    assert_nodes(test_block, expected_block)
