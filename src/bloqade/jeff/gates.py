"""This module holds `canonical`, which reads custom gate names as well-known gates."""

from dataclasses import dataclass

from kirin import ir

from bloqade.jeff.dialects import stmts

NON_HERMITIAN_NAMES = ("s", "t", "sqrt_x", "sqrt_y")
"""This tuple names the well-known gates whose adjoint can carry a `dg` suffix."""

ALIASES = {
    "hadamard": "h",
    "paulix": "x",
    "pauliy": "y",
    "pauliz": "z",
    "sx": "sqrt_x",
    "u3": "u",
}
"""This table maps lower-case custom gate names to well-known gate names."""

CONTROLLED_NAMES = {
    "cx": ("x", 1),
    "cnot": ("x", 1),
    "cy": ("y", 1),
    "cz": ("z", 1),
    "ccx": ("x", 2),
    "toffoli": ("x", 2),
    "ccz": ("z", 2),
}
"""This table maps a controlled custom name to its gate and its number of controls."""


@dataclass(frozen=True)
class Shape:
    """A record of the name, qubits, parameters, adjoint flag and power of a gate."""

    name: str
    targets: tuple[ir.SSAValue, ...]
    controls: tuple[ir.SSAValue, ...]
    params: tuple[ir.SSAValue, ...]
    adjoint: bool
    power: int


def canonical(node: stmts.Gate) -> Shape:
    """Return the well-known shape of the gate `node`.

    If the power of `node` is zero, the shape has power one.
    """
    name = node.gate_name.lower()
    adjoint = bool(node.adjoint)
    if name.endswith("dg"):
        base = ALIASES.get(name[:-2], name[:-2])
        if base in NON_HERMITIAN_NAMES:
            name, adjoint = base, not adjoint
    name = ALIASES.get(name, name)
    targets, controls = tuple(node.targets), tuple(node.controls)
    if name in CONTROLLED_NAMES and not controls:
        name, count = CONTROLLED_NAMES[name]
        controls, targets = targets[:count], targets[count:]
    return Shape(name, targets, controls, tuple(node.params), adjoint, node.power or 1)
