import os

from kirin import ir
from kirin.rewrite import Walk
from kirin.dialects import py

from bloqade import squin
from bloqade.squin import op, qubit, kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStim
from bloqade.squin.rewrite import WrapAddressAnalysis
from bloqade.analysis.address import AddressAnalysis


# Taken gratuitously from Kai's unit test
def codegen(mt: ir.Method):
    # method should not have any arguments!
    emit = EmitStimMain()
    emit.initialize()
    emit.run(mt=mt, args=())
    return emit.get_output()


def as_int(value: int):
    return py.constant.Constant(value=value)


def as_float(value: float):
    return py.constant.Constant(value=value)


def load_reference_program(filename):
    path = os.path.join(
        os.path.dirname(__file__), "stim_reference_programs", "qubit", filename
    )
    with open(path, "r") as f:
        return f.read()


def run_address_and_stim_passes(test):
    addr_frame, _ = AddressAnalysis(test.dialects).run_analysis(test)
    Walk(WrapAddressAnalysis(address_analysis=addr_frame.entries)).rewrite(test.code)
    SquinToStim(test.dialects)(test)


def test_qubit():
    @kernel
    def test():
        n_qubits = 2
        ql = qubit.new(n_qubits)
        qubit.broadcast(op.h(), ql)
        qubit.apply(op.x(), ql[0])
        ctrl = op.control(op.x(), n_controls=1)
        qubit.apply(ctrl, ql[1], ql[0])
        # measure out
        squin.qubit.measure(ql)
        return

    run_address_and_stim_passes(test)
    base_stim_prog = load_reference_program("qubit.txt")

    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_reset():
    @kernel
    def test():
        n_qubits = 1
        q = qubit.new(n_qubits)
        # reset the qubit
        squin.qubit.apply(op.reset(), q[0])
        # measure out
        squin.qubit.measure(q[0])
        return

    run_address_and_stim_passes(test)
    base_stim_prog = load_reference_program("qubit_reset.txt")

    assert codegen(test) == base_stim_prog.rstrip()


def test_qubit_broadcast():
    @kernel
    def test():
        n_qubits = 4
        ql = qubit.new(n_qubits)
        # apply Hadamard to all qubits
        squin.qubit.broadcast(op.h(), ql)
        # measure out
        squin.qubit.measure(ql)
        return

    run_address_and_stim_passes(test)
    base_stim_prog = load_reference_program("qubit_broadcast.txt")

    assert codegen(test) == base_stim_prog.rstrip()
