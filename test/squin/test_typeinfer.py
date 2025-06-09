from kirin import ir
from kirin.types import Any, Literal
from kirin.dialects.ilist import IListType
from kirin.analysis.typeinfer import TypeInference

from bloqade import squin
from bloqade.types import QubitType


# stmt_at and results_at taken from kirin type inference tests with
# minimal modification
def stmt_at(kernel: ir.Method, block_id: int, stmt_id: int) -> ir.Statement:
    return kernel.code.body.blocks[block_id].stmts.at(stmt_id)  # type: ignore


def results_at(kernel: ir.Method, block_id: int, stmt_id: int):
    return stmt_at(kernel, block_id, stmt_id).results


# following tests ensure that type inferece for squin.qubit.New can figure
# out the IList length when the data is immediately available. If not, just
# safely fall back to Any. Historically, without an addition to the
# type inference method table, the result type of squin's qubit.new
# would always be IListType[QubitType, Any].
def test_typeinfer_new_qubit_len_concrete():

    @squin.kernel
    def test():
        q = squin.qubit.new(4)
        return q

    type_infer_analysis = TypeInference(dialects=test.dialects)
    frame, _ = type_infer_analysis.run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 1)] == [
        IListType[QubitType, Literal(4)]
    ]


def test_typeinfer_new_qubit_len_ambiguous():
    # Now let's try with non-concrete length
    @squin.kernel
    def test(n: int):
        q = squin.qubit.new(n)
        return q

    type_infer_analysis = TypeInference(dialects=test.dialects)

    frame_ambiguous, _ = type_infer_analysis.run_analysis(test)

    assert [frame_ambiguous.entries[result] for result in results_at(test, 0, 0)] == [
        IListType[QubitType, Any]
    ]


# for a while, MeasureQubit and MeasureQubitList in squin had the exact same argument types
# (IList of qubits) which, along with the wrappers, seemed to cause type inference to
# always return bottom with getitem
def test_typeinfer_new_qubit_getitem():
    @squin.kernel
    def test():
        q = squin.qubit.new(4)
        q0 = q[0]
        q1 = q[1]
        return [q0, q1]

    type_infer_analysis = TypeInference(dialects=test.dialects)
    frame, _ = type_infer_analysis.run_analysis(test)

    assert [frame.entries[result] for result in results_at(test, 0, 3)] == [QubitType]
    assert [frame.entries[result] for result in results_at(test, 0, 5)] == [QubitType]
