import os

from kirin import ir
from kirin.dialects import scf, ilist

from bloqade import squin
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


def load_reference_program(filename):
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "annotate", filename
    )
    with open(path, "r") as f:
        return f.read()


def test_linear_program_rewrite():

    @squin.kernel
    def main():
        n_qubits = 4
        q = squin.qalloc(n_qubits)

        # do some gates
        squin.x(q[0])
        squin.y(q[1])
        squin.z(q[2])
        squin.cx(q[0], q[1])
        # Broadcast control
        squin.broadcast.cx(controls=[q[0], q[2]], targets=[q[1], q[3]])
        # broadcast single qubit gate
        squin.broadcast.z(q)

        # measure everything out
        ms = squin.broadcast.measure(q)

        # use some statements from dialect
        squin.set_detector([ms[0], ms[1]], coordinates=(0.0, 0.0))
        squin.set_detector([ms[1], ms[2]], coordinates=(1.0, 0.0))

        squin.set_observable(measurements=[ms[2]])

        return

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("linear_program_rewrite.stim")

    assert base_stim_prog == codegen(main)


def test_simple_if_rewrite():

    @squin.kernel
    def main():
        n_qubits = 4
        q = squin.qalloc(n_qubits)

        ms = squin.broadcast.measure(q)

        if ms[0]:
            squin.z(q[0])
            squin.broadcast.x([q[1], q[2], q[3]])
            squin.broadcast.z(q)

        if ms[1]:
            squin.x(q[0])
            squin.y(q[1])

        ms1 = squin.broadcast.measure(q)
        squin.set_detector([ms1[0], ms1[1]], coordinates=(0.0, 0.0))
        squin.set_observable(measurements=[ms1[2]])

        return

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("simple_if_rewrite.stim")

    assert base_stim_prog == codegen(main)


def test_if_with_else_rewrite():

    @squin.kernel
    def main():
        n_qubits = 4
        q = squin.qalloc(n_qubits)

        ms = squin.broadcast.measure(q)

        if ms[0]:
            squin.z(q[0])
        else:
            squin.x(q[0])

        return

    assert any(isinstance(stmt, scf.IfElse) for stmt in main.code.regions[0].stmts())


def test_nested_if_rewrite():

    @squin.kernel
    def main():
        n_qubits = 4
        q = squin.qalloc(n_qubits)

        ms = squin.broadcast.measure(q)

        if ms[0]:
            squin.z(q[0])
            if ms[0]:
                squin.x(q[1])

        return

    assert any(isinstance(stmt, scf.IfElse) for stmt in main.code.regions[0].stmts())


def test_nested_for():

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        for i in range(2):
            m = squin.broadcast.measure(q)
            for j in range(2):
                squin.set_detector([m[j]], coordinates=(0, 0))

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("nested_for.stim")

    assert base_stim_prog == codegen(main)


def test_measure_desugar():

    @squin.kernel
    def main():
        q = squin.qalloc(10)

        pairs = ilist.IList([0, 1, 2, 3])

        squin.measure(q[pairs[0]])
        for i in range(1):
            squin.measure(q[0])
            squin.measure(q[i])
            squin.measure(q[pairs[0]])
            squin.measure(q[pairs[i]])

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("measure_desugar.stim")

    assert base_stim_prog == codegen(main)


def test_pick_if_else():

    @squin.kernel
    def main():
        q = squin.qalloc(10)
        if False:
            squin.h(q[0])

        if True:
            squin.h(q[0])

    SquinToStimPass(main.dialects, no_raise=True)(main)

    assert not any(type(stmt) is scf.IfElse for stmt in main.code.regions[0].stmts())


def test_set_detector_with_alias():

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        results = squin.broadcast.measure(q)
        results_2 = results
        squin.set_detector(
            measurements=[results_2[0], results_2[1]], coordinates=(0, 0)
        )

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("set_detector_with_alias.stim")

    assert base_stim_prog == codegen(main)


def test_broadcast_alias():

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        q_2 = q
        squin.broadcast.x(q_2)

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("broadcast_with_alias.stim")

    assert base_stim_prog == codegen(main)


def test_rep_code():

    @squin.kernel
    def entangle(cx_pairs):
        for i in range(len(cx_pairs)):
            controls = cx_pairs[i][::2]
            targets = cx_pairs[i][1::2]
            squin.broadcast.cx(controls, targets)

    @squin.kernel
    def rep_code():

        q = squin.qalloc(5)
        data = q[::2]
        ancilla = q[1::2]

        # reset everything initially
        squin.broadcast.reset(q)

        ## Initial round, entangle data qubits with ancillas.
        ## This entanglement will happen again so it's best we
        ## save the qubit pairs for reuse.
        cx_pair_1 = [data[0], ancilla[0], data[1], ancilla[1]]
        cx_pair_2 = [data[1], ancilla[0], data[2], ancilla[1]]
        cx_pairs = [cx_pair_1, cx_pair_2]

        entangle(cx_pairs)

        # let's measure the ancillas and set detectors
        init_ancilla_meas_res = squin.broadcast.measure(ancilla)
        for i in range(len(init_ancilla_meas_res)):
            squin.set_detector(
                measurements=[init_ancilla_meas_res[i]], coordinates=(0, 0)
            )

        # let's do a standard round now!
        entangle(cx_pairs)
        round_ancilla_meas_res = squin.broadcast.measure(ancilla)
        for i in range(len(init_ancilla_meas_res)):
            squin.set_detector(
                measurements=[init_ancilla_meas_res[i], round_ancilla_meas_res[i]],
                coordinates=(0, 0),
            )

        # Let's make this one a bit noisy (:
        entangle(cx_pairs)

        controls = cx_pairs[0][::2]
        targets = cx_pairs[0][1::2]
        squin.broadcast.depolarize2(p=0.01, controls=controls, targets=targets)
        squin.broadcast.qubit_loss(0.001, q)

        new_round_ancilla_meas_res = squin.broadcast.measure(ancilla)
        for i in range(len(new_round_ancilla_meas_res)):
            squin.set_detector(
                measurements=[round_ancilla_meas_res[i], new_round_ancilla_meas_res[i]],
                coordinates=(0, 0),
            )

        # finally we want to measure out the data qubits and set final detectors
        # The idea is to assert parity of your data qubits with the final round of measurement results
        data_meas_res = squin.broadcast.measure(data)
        squin.set_detector(
            measurements=[
                data_meas_res[0],
                data_meas_res[1],
                new_round_ancilla_meas_res[0],
            ],
            coordinates=(0, 0),
        )
        squin.set_detector(
            measurements=[
                data_meas_res[1],
                data_meas_res[2],
                new_round_ancilla_meas_res[1],
            ],
            coordinates=(0, 0),
        )

        # Now we want to dictate a measurement as the observable
        squin.set_observable(measurements=[data_meas_res[-1]])

    SquinToStimPass(rep_code.dialects)(rep_code)

    base_stim_prog = load_reference_program("rep_code.stim")

    assert base_stim_prog == codegen(rep_code)


def test_detector_coords_as_args():

    @squin.kernel
    def func(m, x: tuple):
        squin.set_detector(m, coordinates=x)

    @squin.kernel
    def main():
        q = squin.qalloc(2)
        m = squin.broadcast.measure(q)

        x = 5.0
        y = [3, 4]
        z = (1, 2, x)

        squin.set_detector(m, coordinates=(0, 1))
        squin.set_detector(m, coordinates=y)  # [3, 4]
        squin.set_detector(m, coordinates=(0, x))  # (0, 5.0)
        squin.set_detector(m, coordinates=(x, y[0]))  # (5.0, 3)
        squin.set_detector(m, coordinates=z)  # (1, 2, 5.0)
        squin.set_detector(m, coordinates=z[:2])  # (1, 2)

        func(m, z)  # (1, 2, 5.0)

    SquinToStimPass(main.dialects)(main)

    base_stim_prog = load_reference_program("detector_coords_as_args.stim")

    assert base_stim_prog == codegen(main)
