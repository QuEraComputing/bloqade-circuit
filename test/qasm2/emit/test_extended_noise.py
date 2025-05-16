from bloqade import noise, qasm2


@qasm2.extended
def main():
    qreg = qasm2.qreg(4)

    qasm2.cx(qreg[0], qreg[1])
    qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)

    noise.native.pauli_channel(qargs=[qreg[0], qreg[1]], px=0.1, py=0.2, pz=0.3)

    qasm2.u(qreg[2], theta=0.1, phi=0.2, lam=0.3)


main.print()

target = qasm2.emit.QASM2(allow_noise=True)
ast = target.emit(main)
qasm2.parse.pprint(ast)
