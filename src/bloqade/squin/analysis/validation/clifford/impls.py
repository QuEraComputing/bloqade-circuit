from kirin import interp
from kirin.lattice import EmptyLattice
from kirin.analysis import ForwardFrame

from bloqade.squin import gate
from bloqade.analysis.validation.clifford import _CliffordValidationAnalysis


@gate.dialect.register(key="validate.clifford")
class _GateMethods(interp.MethodTable):
    @interp.impl(gate.stmts.T)
    @interp.impl(gate.stmts.Rx)
    @interp.impl(gate.stmts.Ry)
    @interp.impl(gate.stmts.Rz)
    @interp.impl(gate.stmts.U3)
    @interp.impl(gate.stmts.PhasedXZ)
    def non_clifford_gate(
        self,
        interp_: _CliffordValidationAnalysis,
        frame: ForwardFrame[EmptyLattice],
        stmt: gate.stmts.Gate,
    ):
        interp_.collect_error(stmt)
