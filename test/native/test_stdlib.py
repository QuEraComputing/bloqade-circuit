from bloqade.squin import qubit
from bloqade.native import kernel, stdlib


@kernel
def main():
    qreg = qubit.new(5)

    stdlib.h(qreg[0])
    for i in range(len(qreg)):
        stdlib.cx(qreg[0], qreg[i])
