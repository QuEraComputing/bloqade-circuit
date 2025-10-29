import os

from kirin import ir
from kirin.dialects import py, debug

from bloqade.squin import kernel
from bloqade.stim.emit import EmitStimMain
from bloqade.stim.passes import SquinToStimPass


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
        os.path.dirname(__file__), "stim_reference_programs", "debug", filename
    )
    with open(path, "r") as f:
        return f.read()


def test_info():
    @kernel
    def test():
        debug.info("debug message")
        return

    SquinToStimPass(test.dialects)(test)
    base_stim_prog = load_reference_program("debug.stim")
    assert codegen(test) == base_stim_prog.rstrip()
