"""This module holds the gate shapes that squin supports and their squin statements."""

from bloqade.jeff.gates import Shape
from bloqade.squin.gate import stmts as gate_stmts

SINGLE = {
    "x": gate_stmts.X,
    "y": gate_stmts.Y,
    "z": gate_stmts.Z,
    "h": gate_stmts.H,
}
NON_HERMITIAN = {
    "s": gate_stmts.S,
    "t": gate_stmts.T,
    "sqrt_x": gate_stmts.SqrtX,
    "sqrt_y": gate_stmts.SqrtY,
}
ROTATION = {
    "rx": gate_stmts.Rx,
    "ry": gate_stmts.Ry,
    "rz": gate_stmts.Rz,
}
CONTROLLED = {
    "x": gate_stmts.CX,
    "y": gate_stmts.CY,
    "z": gate_stmts.CZ,
}


ARITY: dict[str, tuple[int, int]] = {
    "i": (1, 0),
    "gphase": (0, 1),
    "u": (1, 3),
    "swap": (2, 0),
    **{name: (1, 0) for name in (*SINGLE, *NON_HERMITIAN)},
    **{name: (1, 1) for name in ROTATION},
}
"""This table maps each uncontrolled gate to its counts of targets and parameters."""


def gate_supported(shape: Shape) -> bool:
    """Return True if squin has a statement for the gate shape `shape`.

    The identity and an uncontrolled global phase count as supported.
    The conversion drops both.
    """
    if shape.power < 1:
        return False
    controls = len(shape.controls)
    if controls == 1 and shape.name in CONTROLLED:
        expected = (1, 0)
    elif controls == 2 and shape.name == "z":
        expected = (1, 0)
    elif controls == 0 and shape.name in ARITY:
        expected = ARITY[shape.name]
    else:
        return False
    return expected == (len(shape.targets), len(shape.params))
