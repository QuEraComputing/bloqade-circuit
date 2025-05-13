import pathlib
import tempfile
import textwrap

from kirin import ir, types
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


def test_loadfile():

    with tempfile.TemporaryDirectory() as tmp_dir:
        with open(f"{tmp_dir}/test.qasm", "w") as f:
            f.write(lines)

        file = pathlib.Path(f"{tmp_dir}/test.qasm")
        qasm2.loadfile(file)


def test_negative_lowering():

    mwe = """
    OPENQASM 2.0;
    include "qelib1.inc";
    qreg q[1];
    rz(-0.2) q[0];
    """

    entry = qasm2.loads(mwe)

    body = ir.Region(
        ir.Block(
            [
                (size := qasm2.expr.ConstInt(value=1)),
                (qreg := qasm2.core.QRegNew(n_qubits=size.result)),
                (phi := qasm2.expr.ConstFloat(value=0.2)),
                (theta := qasm2.expr.Neg(phi.result)),
                (idx := qasm2.expr.ConstInt(value=0)),
                (qubit := qasm2.core.QRegGet(qreg.result, idx.result)),
                (qasm2.uop.RZ(qubit.result, theta.result)),
                (none := func.ConstantNone()),
                (func.Return(none.result)),
            ]
        )
    )

    code = func.Function(
        sym_name="main",
        signature=func.Signature((), types.NoneType),
        body=body,
    )

    code.print()
    entry.print()

    assert entry.code.is_structurally_equal(code)
