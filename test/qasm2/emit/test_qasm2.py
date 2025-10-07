from bloqade import qasm2


def test_qasm2_custom_gate():
    @qasm2.gate
    def custom_gate(a: qasm2.Qubit, b: qasm2.Qubit):
        qasm2.cx(a, b)

    @qasm2.gate
    def custom_gate2(a: qasm2.Bit, b: qasm2.Bit):
        return

    @qasm2.main
    def main():
        qreg = qasm2.qreg(4)
        creg = qasm2.creg(2)
        qasm2.cx(qreg[0], qreg[1])
        qasm2.reset(qreg[0])
        qasm2.measure(qreg[0], creg[0])
        if creg[0] == 1:
            qasm2.reset(qreg[1])
        custom_gate(qreg[0], qreg[1])
        custom_gate2(creg[0], creg[1])
        custom_gate(qreg[1], qreg[2])

    # main.print()
    # custom_gate.print()
    # custom_gate2.print()

    target = qasm2.emit.QASM2(custom_gate=True)
    ast = target.emit(main)
    qasm2.parse.pprint(ast)
