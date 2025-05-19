from bloqade import noise, qasm2


def test_pauli_ch():

    @qasm2.extended
    def main():
        qreg = qasm2.qreg(4)

        qasm2.cx(qreg[0], qreg[1])
        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

        noise.native.pauli_channel(qargs=[qreg[0], qreg[1]], px=0.1, py=0.2, pz=0.3)

        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)


    main.print()

    target = qasm2.emit.QASM2(allow_noise=True)
    out = target.emit_str(main)
    
    expected = """OPENQASM 2.0;
include "qelib1.inc";
qreg qreg[4];
CX qreg[0], qreg[1];
U(0.1, 0.2, 0.3) qreg[2];
// native.PauliChannel(px=0.1, py=0.2, pz=0.3)
//  -: qargs: qreg[0], qreg[1]
U(0.1, 0.2, 0.3) qreg[2];
"""

    assert out == expected


def test_pauli_ch_para():

    @qasm2.extended
    def main():
        qreg = qasm2.qreg(4)

        qasm2.cx(qreg[0], qreg[1])
        qasm2.parallel.u([qreg[2],qreg[3]], theta=0.1, phi=0.2, lam=0.3)

        noise.native.pauli_channel(qargs=[qreg[0], qreg[1]], px=0.1, py=0.2, pz=0.3)

        qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)


    main.print()

    target = qasm2.emit.QASM2(allow_noise=True, allow_parallel=True)
    out = target.emit_str(main)
    expected = """KIRIN {func,lowering.call,lowering.func,native,py.ilist,qasm2.core,qasm2.expr,qasm2.indexing,qasm2.parallel,qasm2.uop,scf};
include "qelib1.inc";
qreg qreg[4];
CX qreg[0], qreg[1];
parallel.U(0.1, 0.2, 0.3) {
  qreg[2];
  qreg[3];
}
// native.PauliChannel(px=0.1, py=0.2, pz=0.3)
//  -: qargs: qreg[0], qreg[1]
U(0.1, 0.2, 0.3) qreg[2];
"""

    assert out == expected


