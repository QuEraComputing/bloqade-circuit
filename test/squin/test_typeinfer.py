import pytest
from kirin import ir
from kirin.types import Any, Bottom, Literal
from kirin.dialects.ilist import IListType
from kirin.analysis.typeinfer import TypeInference

from bloqade import squin
from bloqade.types import QubitType, MeasurementResultType


# stmt_at and results_at taken from kirin type inference tests with
# minimal modification
def stmt_at(kernel: ir.Method, block_id: int, stmt_id: int) -> ir.Statement:
    return kernel.code.body.blocks[block_id].stmts.at(stmt_id)  # type: ignore


def results_at(kernel: ir.Method, block_id: int, stmt_id: int):
    return stmt_at(kernel, block_id, stmt_id).results


# following tests ensure that type inferece for squin.qubit.New can figure
# out the IList length when the data is immediately available. If not, just
# safely fall back to Any. Historically, without an addition to the
# type inference method table, the result type of squin's qalloc
# would always be IListType[QubitType, Any].
@pytest.mark.xfail
def test_typeinfer_new_qubit_len_concrete():

    @squin.kernel
    def test():
        q = squin.qalloc(4)
        return q

    type_infer_analysis = TypeInference(dialects=test.dialects)
    frame, _ = type_infer_analysis.run(test)

    assert [frame.entries[result] for result in results_at(test, 0, 1)] == [
        IListType[QubitType, Literal(4)]
    ]


def test_typeinfer_new_qubit_len_ambiguous():
    # Now let's try with non-concrete length
    @squin.kernel
    def test(n: int):
        q = squin.qalloc(n)
        return q

    type_infer_analysis = TypeInference(dialects=test.dialects)

    frame_ambiguous, _ = type_infer_analysis.run(test)

    assert [frame_ambiguous.entries[result] for result in results_at(test, 0, 0)] == [
        IListType[QubitType, Any]
    ]


# for a while, MeasureQubit and MeasureQubitList in squin had the exact same argument types
# (IList of qubits) which, along with the wrappers, seemed to cause type inference to
# always return bottom with getitem
def test_typeinfer_new_qubit_getitem():
    @squin.kernel
    def test():
        q = squin.qalloc(4)
        q0 = q[0]
        q1 = q[1]
        return [q0, q1]

    type_infer_analysis = TypeInference(dialects=test.dialects)
    frame, _ = type_infer_analysis.run(test)

    assert [frame.entries[result] for result in results_at(test, 0, 3)] == [QubitType]
    assert [frame.entries[result] for result in results_at(test, 0, 5)] == [QubitType]


def test_typeinfer_measure():
    @squin.kernel
    def single_qubit():
        q = squin.qalloc(1)
        return squin.measure(q[1])

    assert single_qubit.return_type.is_structurally_equal(MeasurementResultType)

    @squin.kernel
    def many_qubits():
        q = squin.qalloc(4)
        return squin.broadcast.measure(q)

    assert many_qubits.return_type.is_subseteq(IListType[MeasurementResultType])
    assert not many_qubits.return_type.is_subseteq(Bottom)

    @squin.kernel
    def wrong():
        q = squin.qalloc(4)
        return squin.measure(q)

    assert wrong.return_type.is_subseteq(Bottom)
