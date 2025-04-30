from bloqade import qasm2
from bloqade.qasm2.emit import QASM2  # the QASM2 target
from bloqade.qasm2.parse import Console, spprint  # the QASM2 pretty printer

# from qiskit import QuantumCircuit
# from src.helper import get_qasm_string


@qasm2.extended
def kernel():
    # This uses a QASM2 keyword in its output
    ## Must be some kind of alias statement
    ## that disappears somewhere, could catch things
    ## there
    qreg = qasm2.qreg(4)
    qasm2.cx(qreg[0], qreg[1])


target = QASM2()
# In the construction of the AST there
# has to be a way to catch the problematic
# names and manipulate them before they get
# traversed and produced an invalid QASM program
# string...
qasm_ast = target.emit(kernel)
qasm = spprint(
    qasm_ast,
    console=Console(
        no_color=True,
        force_jupyter=False,
        force_interactive=False,
        force_terminal=False,
    ),
)
# print(qasm_ast)
print(qasm)


# circuit = QuantumCircuit.from_qasm_str(qasm)
