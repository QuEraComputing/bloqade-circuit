from bloqade import qasm2
from bloqade.qasm2.emit import QASM2


def test_unrolling_ifs():
    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.measure(q[0], c[0])

        if c[0] == 1:
            qasm2.x(q[0])
            qasm2.x(q[1])

        return q

    main.print()

    target = QASM2()
    ast = target.emit(main)

    qasm2.parse.pprint(ast)

    @qasm2.main
    def main_unrolled():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.measure(q[0], c[0])

        if c[0] == 1:
            qasm2.x(q[0])
        if c[0] == 1:
            qasm2.x(q[1])

        return q

    main_unrolled.print()

    target = QASM2()
    ast_unrolled = target.emit(main_unrolled)

    qasm2.parse.pprint(ast_unrolled)


def test_nested_kernels():
    @qasm2.main
    def nested(q: qasm2.QReg, c: qasm2.CReg):
        qasm2.h(q[0])

        qasm2.measure(q, c)
        if c[0] == 1:
            qasm2.x(q[0])
            qasm2.x(q[1])

        return q

    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        nested(q, c)

        return c

    target = QASM2()
    ast = target.emit(main)

    qasm2.parse.pprint(ast)


def test_conditional_nested_kernel():
    @qasm2.main
    def nested(q: qasm2.QReg, c: qasm2.CReg):
        qasm2.h(q[0])

        qasm2.measure(q, c)

        qasm2.x(q[0])
        qasm2.x(q[1])

        return q

    @qasm2.main
    def main():
        q = qasm2.qreg(2)
        c = qasm2.creg(2)

        qasm2.h(q[0])
        qasm2.measure(q, c)

        if c[0] == 1:
            nested(q, c)

        return c

    target = QASM2(unroll_ifs=True)
    ast = target.emit(main)

    qasm2.parse.pprint(ast)
