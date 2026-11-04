"""Merge each run of native single-qubit rotations into at most one `R` and one `Rz`.

A run is a chain of native `R` and `Rz` statements with constant angles in which
each statement consumes exactly the wire or register outputs of the statement
before it. So every statement of a run acts on the same qubits, and a merge never
splits a broadcast. A broadcast is one parallel pulse on the hardware, and splitting
it can cost more pulses than a merge saves.

The rule multiplies a run as an SU(2) matrix and emits at most `R(phi, theta)` then
`Rz(lam)`. It uses the identity `Rz(a) Rx(theta) Rz(b) = Rz(a + b) R(-b, theta)`,
with angles in turns. The method and the decomposition follow bloqade-lanes PR 1118:
https://github.com/QuEraComputing/bloqade-lanes/pull/1118

The rule reads the angles as constants, so constant folding must run first.
"""

import math

import numpy as np
from kirin import ir
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.constants import constant_float
from bloqade.squin.wire import stmts
from bloqade.squin.wire.kinds import GateKind

TOLERANCE = 1e-9
"""Give the largest size of a matrix entry that counts as zero.

The same bound decides whether an angle sits on the grid of `GRID`.
"""

GRID = 4096
"""Snap an angle within `TOLERANCE` of a multiple of `1 / GRID` turns onto it.

The matrix arithmetic leaves a Clifford angle as `0.24999999999999997`. Snapping
gives back `0.25`, so equal angles get equal constants.
"""

ROTATION_TYPES = (stmts.Gate, stmts.RegisterGate)
"""Hold the statement classes that can carry a native rotation."""

Spec = tuple[tuple[GateKind, tuple[float, ...]], ...]
"""Hold the gates of a merged run in time order, such as `((NATIVE_R, (phi, theta)),)`."""


def rotation_matrix(node: ir.Statement) -> np.ndarray | None:
    """Return the SU(2) matrix of a native rotation with constant angles, or None.

    `Rz(t)` is `exp(-i pi t Z)`. `R(phi, theta)` is
    `exp(-i pi theta (cos(2 pi phi) X + sin(2 pi phi) Y))`. The PyQrack methods
    in `bloqade/pyqrack/native.py` apply the same matrices.
    """
    if not isinstance(node, ROTATION_TYPES):
        return None
    if node.kind not in (GateKind.NATIVE_R, GateKind.NATIVE_RZ):
        return None
    angles = [constant_float(value) for value in node.params]
    if any(angle is None for angle in angles):
        return None
    if node.kind is GateKind.NATIVE_RZ:
        (turns,) = angles
        assert turns is not None
        phase = np.exp(-1j * math.pi * turns)
        matrix = np.array([[phase, 0], [0, phase.conjugate()]])
    else:
        phi, theta = angles
        assert phi is not None and theta is not None
        c, s = math.cos(math.pi * theta), math.sin(math.pi * theta)
        axis = np.exp(1j * math.tau * phi)
        matrix = np.array([[c, -1j * s * axis.conjugate()], [-1j * s * axis, c]])
    return matrix.conj().T if node.adjoint else matrix


def snap(turns: float) -> float:
    """Reduce an angle in turns modulo 1 and move float noise onto the grid."""
    snapped = round(turns * GRID) / GRID
    if abs(snapped - turns) < TOLERANCE:
        turns = snapped
    turns %= 1.0
    return 0.0 if abs(turns - 1.0) < TOLERANCE else turns


def decompose(unitary: np.ndarray) -> Spec:
    """Write a 2x2 unitary as `R(phi, theta)` then `Rz(lam)`, up to a global phase.

    The result drops each gate that is the identity. So the identity gives no gate,
    and a diagonal matrix gives one `Rz`. `theta` lies in `[0, 0.5]`, and `phi` and
    `lam` lie in `[0, 1)`.
    """
    # Up to a global phase g, Rz(lam) R(phi, theta) has these entries, with
    # c = cos(pi theta) and s = sin(pi theta):
    #   u00 = g e^{-i pi lam} c          u11 = g e^{i pi lam} c
    #   u10 = -i g e^{i pi lam} e^{2 pi i phi} s
    #   u01 = -i g e^{-i pi lam} e^{-2 pi i phi} s
    (u00, u01), (u10, u11) = unitary
    c, s = abs(u00), abs(u10)
    if s < TOLERANCE:
        lam = snap(np.angle(u11 / u00) / math.tau)
        return () if lam == 0.0 else ((GateKind.NATIVE_RZ, (lam,)),)
    theta = snap(math.atan2(s, c) / math.pi)
    if c < TOLERANCE:
        # With c = 0, the matrix fixes only the sum lam + 2 phi. So lam is 0, and
        # phi carries the whole sum.
        lam = 0.0
        phi = snap(np.angle(u10 / u01) / (2 * math.tau))
    else:
        lam = snap(np.angle(u11 / u00) / math.tau)
        phi = snap(np.angle(1j * u10 / u00 * np.exp(-1j * math.tau * lam)) / math.tau)
    spec: Spec = ((GateKind.NATIVE_R, (phi, theta)),)
    return spec if lam == 0.0 else spec + ((GateKind.NATIVE_RZ, (lam,)),)


def successor(node: stmts.Operation) -> stmts.Operation | None:
    """Return the rotation that consumes exactly every output of `node`, or None.

    The next statement must have the class of `node`, constant angles, and the
    outputs of `node` as its linear operands, in any order.
    """
    outputs = node.outputs
    if not outputs or any(len(output.uses) != 1 for output in outputs):
        return None
    use, *_ = outputs[0].uses
    after = use.stmt
    if type(after) is not type(node) or after.parent_block is not node.parent_block:
        return None
    assert isinstance(after, stmts.Operation)
    if set(after.linear) != set(outputs) or rotation_matrix(after) is None:
        return None
    return after


def predecessor(node: stmts.Operation) -> stmts.Operation | None:
    """Return the rotation whose `successor` is `node`, or None."""
    before = node.linear[0].owner if node.linear else None
    if not isinstance(before, stmts.Operation) or rotation_matrix(before) is None:
        return None
    return before if successor(before) is node else None


def pulses(spec: Spec) -> tuple[int, int]:
    """Return the count of `R` statements and the count of all statements of `spec`."""
    return sum(kind is GateKind.NATIVE_R for kind, _ in spec), len(spec)


class MergeRotations(RewriteRule):
    """Replace each run of native rotations with its merged form.

    The rule starts at the first statement of a run. It rewrites the run only if
    the merged form has fewer `R` statements, or as many `R` statements and fewer
    statements in total. So it leaves a run such as `R` then `Rz` alone. The merged
    statements sit just before the last statement of the run.
    """

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Merge the run that starts at `node`, if merging it pays."""
        if not isinstance(node, stmts.Operation) or rotation_matrix(node) is None:
            return RewriteResult()
        if predecessor(node) is not None:
            return RewriteResult()
        run = [node]
        while (after := successor(run[-1])) is not None:
            run.append(after)
        if len(run) < 2:
            return RewriteResult()
        unitary = np.eye(2, dtype=complex)
        for gate in run:
            matrix = rotation_matrix(gate)
            assert matrix is not None
            unitary = matrix @ unitary
        merged = decompose(unitary)
        kinds = [gate.kind for gate in run if isinstance(gate, ROTATION_TYPES)]
        before = (kinds.count(GateKind.NATIVE_R), len(kinds))
        if pulses(merged) >= before:
            return RewriteResult()
        emit(run, merged)
        return RewriteResult(has_done_something=True)


def emit(run: list[stmts.Operation], merged: Spec) -> None:
    """Insert `merged` on the inputs of `run` and delete the statements of `run`.

    A statement of the run can list its qubits in another order than the statement
    before it. So the function follows each qubit from its input in the first
    statement to its output in the last statement.
    """
    first, last = run[0], run[-1]
    start = first.linear
    # Map the latest value of each qubit to the position of its input in `start`.
    position: dict[ir.SSAValue, int] = {value: k for k, value in enumerate(start)}
    for gate in run:
        position = {
            output: position[value]
            for value, output in zip(gate.linear, gate.outputs, strict=True)
        }
    current = list(start)
    for kind, angles in merged:
        params = []
        for angle in angles:
            constant = py.Constant(angle)
            constant.insert_before(last)
            params.append(constant.result)
        if isinstance(first, stmts.RegisterGate):
            made: stmts.Operation = stmts.RegisterGate(
                kind, tuple(current), tuple(params)
            )
        else:
            made = stmts.Gate(kind, tuple(current), tuple(params))
        made.insert_before(last)
        for output, value in zip(made.outputs, current, strict=True):
            output.type = value.type
        current = list(made.outputs)
    for output, k in position.items():
        output.replace_by(current[k])
    for gate in reversed(run):
        gate.delete()
