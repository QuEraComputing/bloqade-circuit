import math

from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardFrame

from bloqade.squin import gate
from bloqade.squin.rewrite import SquinU3ToClifford
from bloqade.analysis.validation.clifford import _CliffordAnalysis

# Reused as the single source of truth for which rotation/U3 angles the
# squin -> stim pipeline can turn into Clifford gates.
_u3_to_clifford = SquinU3ToClifford()


def _rotation_is_clifford(stmt: gate.stmts.RotationGate) -> bool:
    angle = _u3_to_clifford.get_constant(stmt.angle)
    if angle is None:
        return False
    return _u3_to_clifford.resolve_angle(angle * math.tau) is not None


@gate.dialect.register(key="validate.clifford")
class _GateMethods(interp.MethodTable):
    @interp.impl(gate.stmts.T)
    @interp.impl(gate.stmts.PhasedXZ)
    def non_clifford_gate(
        self,
        interp_: _CliffordAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.Gate,
    ):
        interp_.collect_errors(stmt)

    @interp.impl(gate.stmts.Rx)
    @interp.impl(gate.stmts.Ry)
    @interp.impl(gate.stmts.Rz)
    def rotation_gate(
        self,
        interp_: _CliffordAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.RotationGate,
    ):
        if not _rotation_is_clifford(stmt):
            interp_.collect_errors(stmt)

    @interp.impl(gate.stmts.U3)
    def u3_gate(
        self,
        interp_: _CliffordAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.U3,
    ):
        if not _u3_to_clifford.decompose_U3_gates(stmt):
            interp_.collect_errors(stmt)
