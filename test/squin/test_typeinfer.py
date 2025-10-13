from kirin import ir
from kirin.types import Any, Literal
from kirin.dialects import func
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


def test_generic_rot():
    @squin.kernel(fold=False)
    def main():
        z = squin.op.z()
        squin.op.rot(axis=z, angle=0.123)

    main.print()

    for stmt in main.callable_region.blocks[0].stmts:
        if isinstance(stmt, squin.op.stmts.Rot):
            assert stmt.result.type.is_subseteq(squin.op.types.RzOpType)
            assert stmt.result.type.is_subseteq(squin.op.types.CompositeOpType)
            assert stmt.result.type.is_subseteq(squin.op.types.OpType)


def test_generic_control():
    @squin.kernel(fold=False)
    def main():
        z = squin.op.z()
        squin.op.control(z, n_controls=1)
        squin.op.cz()

    main.print()

    for stmt in main.callable_region.blocks[0].stmts:
        if isinstance(stmt, (squin.op.stmts.Control, func.Invoke)):
            assert stmt.result.type.is_subseteq(squin.op.types.CZOpType)
            assert stmt.result.type.is_subseteq(squin.op.types.CompositeOpType)
            assert stmt.result.type.is_subseteq(squin.op.types.OpType)


def test_mult():

    @squin.kernel(fold=False)
    def main():
        rx = squin.op.rx(1.0)
        return rx * rx

    main.print()

    for stmt in main.callable_region.blocks[0].stmts:
        if isinstance(stmt, squin.op.stmts.Mult):
            assert stmt.result.type.is_subseteq(squin.op.types.OpType)
            assert stmt.result.type.is_subseteq(squin.op.types.BinaryOpType)
            assert stmt.result.type.is_subseteq(
                squin.op.types.MultType[
                    squin.op.types.RxOpType, squin.op.types.RxOpType
                ]
            )

    @squin.kernel(fold=False)
    def main2():
        rx = squin.op.rx(1.0)
        rz = squin.op.rz(1.123)
        return rx * rz

    for stmt in main2.callable_region.blocks[0].stmts:
        if isinstance(stmt, squin.op.stmts.Mult):
            assert stmt.result.type.is_subseteq(squin.op.types.OpType)
            assert stmt.result.type.is_subseteq(squin.op.types.BinaryOpType)
            assert stmt.result.type.is_subseteq(
                squin.op.types.MultType[
                    squin.op.types.RxOpType, squin.op.types.RzOpType
                ]
            )


def test_kron():

    @squin.kernel(fold=False)
    def main():
        rx = squin.op.rx(1.0)
        return squin.op.kron(rx, rx)

    main.print()

    for stmt in main.callable_region.blocks[0].stmts:
        if isinstance(stmt, squin.op.stmts.Mult):
            assert stmt.result.type.is_subseteq(squin.op.types.OpType)
            assert stmt.result.type.is_subseteq(squin.op.types.BinaryOpType)
            assert stmt.result.type.is_subseteq(
                squin.op.types.KronType[
                    squin.op.types.RxOpType, squin.op.types.RxOpType
                ]
            )

    @squin.kernel(fold=False)
    def main2():
        rx = squin.op.rx(1.0)
        rz = squin.op.rz(1.123)
        return squin.op.kron(rx, rz)

    for stmt in main2.callable_region.blocks[0].stmts:
        if isinstance(stmt, squin.op.stmts.Mult):
            assert stmt.result.type.is_subseteq(squin.op.types.OpType)
            assert stmt.result.type.is_subseteq(squin.op.types.BinaryOpType)
            assert stmt.result.type.is_subseteq(
                squin.op.types.KronType[
                    squin.op.types.RxOpType, squin.op.types.RzOpType
                ]
            )
