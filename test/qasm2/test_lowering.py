import textwrap

from kirin.dialects import func

from bloqade import qasm2
from bloqade.qasm2.parse.lowering import QASM2

lines = textwrap.dedent(
    """
OPENQASM 2.0;

qreg q[2];
creg c[2];

h q[0];
CX q[0], q[1];
barrier q[0], q[1];
CX q[0], q[1];
rx(pi/2) q[0];
"""
)


def test_run_lowering():
    ast = qasm2.parse.loads(lines)
    code = QASM2(qasm2.main).run(ast)
    code.print()


def test_loads():

    kernel = QASM2(qasm2.main).loads(lines, "test", returns="c")
    qasm2.main.run_pass(kernel)  # type: ignore
    assert isinstance((ret := kernel.callable_region.blocks[0].last_stmt), func.Return)
    assert ret.value.type.is_equal(qasm2.types.CRegType)
