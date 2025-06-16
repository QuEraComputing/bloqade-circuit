import math
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


def test_gate():
    qasm2_prog = textwrap.dedent(
        """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[2];
        gate custom_gate q1, q2 {
            cx q1, q2;
        }
        h q[0];
        custom_gate q[0], q[1];
        """
    )

    main = qasm2.loads(qasm2_prog, compactify=False)

    main.print()

    from bloqade.pyqrack import StackMemorySimulator

    target = StackMemorySimulator(min_qubits=2)
    ket = target.state_vector(main)

    assert ket[1] == ket[2] == 0
    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-6)
    assert math.isclose(abs(ket[3]) ** 2, 0.5, abs_tol=1e-6)


def test_gate_with_params():
    qasm2_prog = textwrap.dedent(
        """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[2];
        h q[1];
        gate custom_gate(theta) q1, q2 {
            u(theta, 0, 0) q1;
            cx q1, q2;
        }
        h q[1];
        custom_gate(1.5707963267948966) q[0], q[1];
        """
    )

    main = qasm2.loads(qasm2_prog, compactify=False)

    main.print()

    from bloqade.pyqrack import StackMemorySimulator

    target = StackMemorySimulator(min_qubits=2)
    ket = target.state_vector(main)

    assert ket[1] == ket[2] == 0
    assert math.isclose(abs(ket[0]) ** 2, 0.5, abs_tol=1e-6)
    assert math.isclose(abs(ket[3]) ** 2, 0.5, abs_tol=1e-6)


def test_if_lowering():

    qasm2_prog = textwrap.dedent(
        """
        OPENQASM 2.0;
        include "qelib1.inc";
        qreg q[1];
        creg c[1];
        if(c == 1) x q[0];
        """
    )

    main = qasm2.loads(qasm2_prog)

    main.print()

    @qasm2.main
    def main2():
        q = qasm2.qreg(1)
        c = qasm2.creg(1)

        if c == 1:
            qasm2.x(q[0])

    main2.print()
