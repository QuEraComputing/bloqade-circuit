from kirin import ir, types
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.ilist import IListType

from bloqade.squin.gate.stmts import SingleQubitGate, RotationGate, ControlledGate, U3, PhasedXZ
from bloqade.squin.noise.stmts import SingleQubitPauliChannel, TwoQubitPauliChannel, Depolarize, Depolarize2, QubitLoss, CorrelatedQubitLoss
from bloqade.qubit.stmts import Measure, Reset

class RemoveEmptyArgGatesRule(RewriteRule):
    def _is_empty_ilist(self, value: ir.SSAValue) -> bool:
        typ = value.type
        if isinstance(typ, IListType):
            _, len_type = typ.vars
            if isinstance(len_type, types.Literal) and len_type.value == 0:
                return True
        return False

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        is_empty = False
        
        if isinstance(node, (SingleQubitGate, RotationGate, U3, PhasedXZ, SingleQubitPauliChannel, Depolarize, QubitLoss, Measure, Reset)):
            # All these have a 'qubits' argument
            if hasattr(node, 'qubits') and self._is_empty_ilist(node.qubits):
                is_empty = True
        elif isinstance(node, (ControlledGate, TwoQubitPauliChannel, Depolarize2)):
            # These have 'controls' and 'targets'
            if (hasattr(node, 'controls') and self._is_empty_ilist(node.controls)) or \
               (hasattr(node, 'targets') and self._is_empty_ilist(node.targets)):
                is_empty = True
        elif isinstance(node, CorrelatedQubitLoss):
            if hasattr(node, 'qubits') and self._is_empty_ilist(node.qubits):
                is_empty = True
                
        if is_empty:
            node.remove()
            return RewriteResult(has_done_something=True)
            
        return RewriteResult()
