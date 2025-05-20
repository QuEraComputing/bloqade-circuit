from bloqade import qasm2
from bloqade.qasm2 import noise


def test_pauli_ch():

    @qasm2.extended
    def main():
        qreg = qasm2.qreg(4)

        qasm2.cx(qreg[0], qreg[1])
        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

        noise.pauli_channel(qargs=[qreg[0], qreg[1]], px=0.1, py=0.2, pz=0.3)

        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

    main.print()

    target = qasm2.emit.QASM2(allow_noise=True)
    out = target.emit_str(main)

    expected = """OPENQASM 2.0;
include "qelib1.inc";
qreg qreg[4];
CX qreg[0], qreg[1];
U(0.1, 0.2, 0.3) qreg[2];
// noise.PauliChannel(px=0.1, py=0.2, pz=0.3)
//  -: qargs: qreg[0], qreg[1]
U(0.1, 0.2, 0.3) qreg[2];
"""

    assert out == expected


def test_pauli_ch_para():

    @qasm2.extended
    def main():
        qreg = qasm2.qreg(4)

        qasm2.cx(qreg[0], qreg[1])
        qasm2.parallel.u([qreg[2], qreg[3]], theta=0.1, phi=0.2, lam=0.3)

        noise.pauli_channel(qargs=[qreg[0], qreg[1]], px=0.1, py=0.2, pz=0.3)

        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

    main.print()

    target = qasm2.emit.QASM2(allow_noise=True, allow_parallel=True)
    out = target.emit_str(main)
    expected = """KIRIN {func,lowering.call,lowering.func,py.ilist,qasm2.core,qasm2.expr,qasm2.indexing,qasm2.noise,qasm2.parallel,qasm2.uop,scf};
include "qelib1.inc";
qreg qreg[4];
CX qreg[0], qreg[1];
parallel.U(0.1, 0.2, 0.3) {
  qreg[2];
  qreg[3];
}
// noise.PauliChannel(px=0.1, py=0.2, pz=0.3)
//  -: qargs: qreg[0], qreg[1]
U(0.1, 0.2, 0.3) qreg[2];
"""

    assert out == expected


def test_loss():

    @qasm2.extended
    def main():
        qreg = qasm2.qreg(4)

        qasm2.cx(qreg[0], qreg[1])
        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

        noise.atom_loss_channel(qargs=[qreg[0], qreg[1]], prob=0.2)

        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

    main.print()

    target = qasm2.emit.QASM2(allow_noise=True)
    out = target.emit_str(main)

    expected = """OPENQASM 2.0;
include "qelib1.inc";
qreg qreg[4];
CX qreg[0], qreg[1];
U(0.1, 0.2, 0.3) qreg[2];
// noise.Atomloss(p=0.2)
//  -: qargs: qreg[0], qreg[1]
U(0.1, 0.2, 0.3) qreg[2];
"""

    assert out == expected


def test_cz_noise():

    @qasm2.extended
    def main():
        qreg = qasm2.qreg(4)

        qasm2.cx(qreg[0], qreg[1])
        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

        noise.cz_pauli_channel(
            ctrls=[qreg[0], qreg[1]],
            qargs=[qreg[2], qreg[3]],
            px_ctrl=0.1,
            py_ctrl=0.2,
            pz_ctrl=0.3,
            px_qarg=0.4,
            py_qarg=0.5,
            pz_qarg=0.6,
            paired=True,
        )

        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

    main.print()

    target = qasm2.emit.QASM2(allow_noise=True)
    out = target.emit_str(main)
    print(out)
    expected = """OPENQASM 2.0;
include "qelib1.inc";
qreg qreg[4];
CX qreg[0], qreg[1];
U(0.1, 0.2, 0.3) qreg[2];
// noise.CZPauliChannel(paired=True, p_ctrl=[x:0.1, y:0.2, z:0.3], p_qarg[x:0.6, y:0.5, z:0.6])
//  -: ctrls: qreg[0], qreg[1]
//  -: qargs: qreg[2], qreg[3]
U(0.1, 0.2, 0.3) qreg[2];
"""

    assert out == expected
