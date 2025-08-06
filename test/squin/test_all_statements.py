from types import ModuleType
from dataclasses import dataclass

from kirin.ir import Statement
from kirin.rewrite import Walk
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade import squin
from bloqade.pyqrack import StackMemorySimulator
from bloqade.analysis import address, measure_id
from bloqade.stim.passes import SquinToStimPass
from bloqade.squin.noise.rewrite import RewriteNoiseStmts
from bloqade.squin.analysis.nsites import NSitesAnalysis


def get_dialect_stmts(module, stmts_module):
    members = [getattr(stmts_module, stmt) for stmt in dir(stmts_module)]

    stmts = set()
    module_dialect = getattr(module, "dialect")
    for member in members:
        try:
            dialect = member.dialect
        except AttributeError:
            # not a stmt
            continue

        if isinstance(member, ModuleType):
            # modules can also have a .dialect attribute
            continue

        if dialect == module_dialect:
            stmts.add(member)

    return stmts


op_stmts = get_dialect_stmts(squin.op, squin.op.stmts)
qubit_stmts = get_dialect_stmts(squin.qubit, squin.qubit)
noise_stmts = get_dialect_stmts(squin.noise, squin.noise.stmts)

# TODO: wire(?)


# NOTE: define the method to be used in all test top-level; DO NOT MODIFY IN TEST!


@squin.kernel(fold=False)
def main():

    ### qubit
    q = squin.qubit.new(5)
    x = squin.op.x()
    squin.qubit.apply(x, q[0])
    squin.qubit.broadcast(x, q)
    squin.qubit.measure(q[1])
    squin.qubit.measure(q)

    ### op
    squin.op.kron(x, x)
    squin.op.mult(x, x)
    squin.op.scale(x, 1.0)
    squin.op.adjoint(x)
    squin.op.control(x, n_controls=1)
    squin.op.reset()
    squin.op.reset_to_one()
    squin.op.identity(sites=2)
    squin.op.rot(x, 0.123)
    squin.op.shift(0.234)
    squin.op.phase(0.234)
    squin.op.x()
    squin.op.y()
    squin.op.z()
    squin.op.sqrt_x()
    squin.op.sqrt_y()
    squin.op.sqrt_z()
    squin.op.h()
    squin.op.s()
    squin.op.t()
    squin.op.p0()
    squin.op.p1()
    squin.op.spin_n()
    squin.op.spin_p()
    squin.op.u(0.234, 1.5, 3.14159)
    squin.op.pauli_string(string="XYZ")

    ### noise
    squin.noise.pauli_error(x, 0.1)
    squin.noise.depolarize(0.1)
    squin.noise.depolarize2(0.1)
    squin.noise.single_qubit_pauli_channel((0.1, 0.2, 0.3))
    two_qubit_pauli_probs = [
        0.023354967892248113,
        0.003247463853107968,
        0.016397706815567816,
        0.05881521942445792,
        0.055273193025446865,
        0.048159912657060724,
        0.06652684300706593,
        0.03042882311429303,
        0.0018064348480710812,
        0.0037171594239370515,
        0.05016247526449243,
        0.037720309303735065,
        0.022077535704784847,
        0.04293521011314487,
        0.01377236173895846,
    ]
    squin.noise.two_qubit_pauli_channel(two_qubit_pauli_probs)
    squin.noise.qubit_loss(0.1)

    ### apply op & noise so that the runtime is actually executed

    ### op
    squin.qubit.apply(squin.op.kron(x, x), q[0], q[1])
    squin.qubit.apply(squin.op.mult(x, x), q[0], q[1])
    squin.qubit.apply(squin.op.scale(x, 1.0), q[0])
    squin.qubit.apply(squin.op.adjoint(x), q[0])
    squin.qubit.apply(squin.op.control(x, n_controls=1), q[0], q[1])
    squin.qubit.apply(squin.op.reset(), q[0])
    squin.qubit.apply(squin.op.reset_to_one(), q[0])
    squin.qubit.apply(squin.op.identity(sites=2), q[0], q[1])
    squin.qubit.apply(squin.op.rot(x, 0.123), q[0])
    squin.qubit.apply(squin.op.shift(0.234), q[0])
    squin.qubit.apply(squin.op.phase(0.234), q[0])
    squin.qubit.apply(squin.op.x(), q[0])
    squin.qubit.apply(squin.op.y(), q[0])
    squin.qubit.apply(squin.op.z(), q[0])
    squin.qubit.apply(squin.op.sqrt_x(), q[0])
    squin.qubit.apply(squin.op.sqrt_y(), q[0])
    squin.qubit.apply(squin.op.sqrt_z(), q[0])
    squin.qubit.apply(squin.op.h(), q[0])
    squin.qubit.apply(squin.op.s(), q[0])
    squin.qubit.apply(squin.op.t(), q[0])
    squin.qubit.apply(squin.op.p0(), q[0])
    squin.qubit.apply(squin.op.p1(), q[0])
    squin.qubit.apply(squin.op.spin_n(), q[0])
    squin.qubit.apply(squin.op.spin_p(), q[0])
    squin.qubit.apply(squin.op.u(0.234, 1.5, 3.14159), q[0])
    squin.qubit.apply(squin.op.pauli_string(string="XYZ"), q[0], q[1], q[2])

    ### noise
    squin.qubit.apply(squin.noise.pauli_error(x, 0.1), q[0])
    squin.qubit.apply(squin.noise.depolarize(0.1), q[0])
    squin.qubit.apply(squin.noise.depolarize2(0.1), q[0], q[1])
    squin.qubit.apply(squin.noise.single_qubit_pauli_channel((0.1, 0.2, 0.3)), q[0])
    squin.qubit.apply(
        squin.noise.two_qubit_pauli_channel(two_qubit_pauli_probs), q[0], q[1]
    )
    squin.qubit.apply(squin.noise.qubit_loss(0.1), q[0])


main.print()


@dataclass
class RemoveUnsupportedStatements(RewriteRule):
    """
    Very unsafe rewrite rule that removes some statements just intended for use in the tests here
    """

    unsupported_statements: tuple[type[Statement], ...]

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        if isinstance(node, self.unsupported_statements):
            node.delete(safe=False)
            return RewriteResult(has_done_something=True)

        if isinstance(
            node,
            squin.qubit.Apply
            | squin.qubit.Broadcast
            | squin.wire.Apply
            | squin.wire.Broadcast,
        ):
            if isinstance(node.operator.owner, self.unsupported_statements):
                node.delete(safe=False)
                return RewriteResult(has_done_something=True)

        return RewriteResult()


def test_all_statements_there():
    main.verify()

    # NOTE: hardcoded list of exclusions which should be rewritten
    should_not_appear = {
        squin.qubit.ApplyAny,
        squin.qubit.MeasureAny,
    }

    main_stmts = main.callable_region.blocks[0].stmts
    main_stmt_types = set(
        [
            type(stmt)
            for stmt in main_stmts
            if stmt.dialect
            in (
                squin.qubit.dialect,
                squin.op.dialect,
                squin.noise.dialect,
                squin.wire.dialect,
            )
        ]
    )

    rem_op_stmts = op_stmts.difference(main_stmt_types)
    rem_op_stmts = rem_op_stmts.difference(should_not_appear)
    assert (
        len(rem_op_stmts) == 0
    ), f"Missing operator statements from kernel: {rem_op_stmts}"

    rem_qubit_stmts = qubit_stmts.difference(main_stmt_types)
    rem_qubit_stmts = rem_qubit_stmts.difference(should_not_appear)
    assert (
        len(rem_qubit_stmts) == 0
    ), f"Missing qubit statements from kernel: {rem_qubit_stmts}"

    # NOTE: special case for noise, where we don't want StochasticUnitaryChannel to appear before the rewrite
    rem_noise_stmts = noise_stmts.difference(main_stmt_types)
    rem_noise_stmts = rem_noise_stmts.difference(should_not_appear)
    assert rem_noise_stmts == {
        squin.noise.stmts.StochasticUnitaryChannel
    }, f"Missing noise statements from kernel: {rem_noise_stmts.difference({squin.noise.stmts.StochasticUnitaryChannel})}"


def test_noise_rewrite():
    main_ = main.similar(main.dialects)
    RewriteNoiseStmts(main_.dialects, no_raise=False)(main_)

    non_rewritable_noise = {
        squin.noise.stmts.StochasticUnitaryChannel,
        squin.noise.stmts.QubitLoss,
    }
    noise_stmts_which_should_be_rewritten = noise_stmts.difference(non_rewritable_noise)

    rewritten_stmts = [
        type(stmt)
        for stmt in main_.callable_region.blocks[0].stmts
        if stmt.dialect
        in (
            squin.qubit.dialect,
            squin.op.dialect,
            squin.noise.dialect,
            squin.wire.dialect,
        )
    ]
    rem_noise_stmts = noise_stmts_which_should_be_rewritten.intersection(
        rewritten_stmts
    )
    assert (
        len(rem_noise_stmts) == 0
    ), f"Noise rewrite failed on statements: {rem_noise_stmts}"


def test_pyqrack():
    sim = StackMemorySimulator(min_qubits=5)
    sim.run(main)

    main.print()


def test_squin2stim():
    main_ = main.similar(main.dialects)

    SquinToStimPass(main_.dialects, no_raise=False).fixpoint(main_)

    main_.print()


def test_cirq_emit():
    # NOTE: hardcoded list of statements that are not supported by cirq
    unsupported_by_cirq = (squin.noise.stmts.QubitLoss,)

    main_ = main.similar(main.dialects)
    rw = Walk(RemoveUnsupportedStatements(unsupported_statements=unsupported_by_cirq))
    rw.rewrite(main_.code)

    circuit = squin.cirq.emit_circuit(main_)

    print(circuit)


def test_address_analysis():
    analysis = address.AddressAnalysis(main.dialects)

    frame, _ = analysis.run_analysis(main, no_raise=False)

    main.print(analysis=frame.entries)


def test_measurement_id_analysis():
    analysis = measure_id.analysis.MeasurementIDAnalysis(main.dialects)

    frame, _ = analysis.run_analysis(main, no_raise=False)

    main.print(analysis=frame.entries)


def test_nsites_analysis():
    analysis = NSitesAnalysis(main.dialects)

    frame, _ = analysis.run_analysis(main, no_raise=False)

    main.print(analysis=frame.entries)
