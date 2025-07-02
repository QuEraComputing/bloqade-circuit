from kirin import ir, types, rewrite
from kirin.dialects import ilist

from bloqade.squin.qubit import Apply, ApplyAny, QubitType
from bloqade.squin.op.types import OpType
from bloqade.squin.rewrite.desugar import ApplyDesugarRule


def test_apply_desugar_rule_single_qubit():

    op = ir.TestValue(OpType)
    qubits = ir.TestValue(QubitType)
    test_block = ir.Block([ApplyAny(operator=op, qubits=(qubits,))])

    expected_block = ir.Block(
        [
            ilist_qubits := ilist.New((qubits,)),
            Apply(operator=op, qubits=ilist_qubits.result),
        ]
    )

    rewrite.Walk(ApplyDesugarRule()).rewrite(test_block)

    assert test_block.is_structurally_equal(expected_block)


def test_apply_desugar_rule_multi_qubit():
    op = ir.TestValue(OpType)
    qubit1 = ir.TestValue(QubitType)
    qubit2 = ir.TestValue(QubitType)
    qubit3 = ir.TestValue(QubitType)
    qubits = (qubit1, qubit2, qubit3)
    test_block = ir.Block([ApplyAny(operator=op, qubits=qubits)])

    expected_block = ir.Block(
        [
            ilist_qubits := ilist.New(qubits),
            Apply(operator=op, qubits=ilist_qubits.result),
        ]
    )

    rewrite.Walk(ApplyDesugarRule()).rewrite(test_block)

    assert test_block.is_structurally_equal(expected_block)


def test_apply_desugar_rule_ilist_qubit():
    op = ir.TestValue(OpType)
    qubits = ir.TestValue(ilist.IListType[QubitType, types.Any])
    test_block = ir.Block([ApplyAny(operator=op, qubits=(qubits,))])

    expected_block = ir.Block([Apply(operator=op, qubits=qubits)])

    rewrite.Walk(ApplyDesugarRule()).rewrite(test_block)

    assert test_block.is_structurally_equal(expected_block)


def test_apply_desugar_rule_fail():
    op = ir.TestValue(OpType)
    qubits = ir.TestValue(types.Any)  # Not a QubitType or IListType of QubitType
    test_block = ir.Block([ApplyAny(operator=op, qubits=(qubits,))])

    expected_block = ir.Block([ApplyAny(operator=op, qubits=(qubits,))])

    assert test_block.is_structurally_equal(
        expected_block
    ), "No changes should be made for non-QubitType inputs"
