from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.qasm2.types import QubitType

from ._dialect import dialect


@statement(dialect=dialect)
class PauliChannel(ir.Statement):

    traits = frozenset({lowering.FromPythonCall()})

    px: float = info.attribute(types.Float)
    py: float = info.attribute(types.Float)
    pz: float = info.attribute(types.Float)
    qargs: ir.SSAValue = info.argument(ilist.IListType[QubitType])

    def check(self):
        probs = (self.px, self.py, self.pz)
        if not all(0 <= p <= 1 for p in probs) or not 0 <= sum(probs) <= 1:
            raise ValueError(f"Invalid Pauli error probabilities (px, py, pz): {probs}")


NumQubits = types.TypeVar("NumQubits")


@statement(dialect=dialect)
class CZPauliChannel(ir.Statement):

    traits = frozenset({lowering.FromPythonCall()})

    paired: bool = info.attribute(types.Bool)
    px_ctrl: float = info.attribute(types.Float)
    py_ctrl: float = info.attribute(types.Float)
    pz_ctrl: float = info.attribute(types.Float)
    px_qarg: float = info.attribute(types.Float)
    py_qarg: float = info.attribute(types.Float)
    pz_qarg: float = info.attribute(types.Float)
    ctrls: ir.SSAValue = info.argument(ilist.IListType[QubitType, NumQubits])
    qargs: ir.SSAValue = info.argument(ilist.IListType[QubitType, NumQubits])

    def check(self):
        probs_ctrl = (self.px_ctrl, self.py_ctrl, self.pz_ctrl)

        def check_prob(p: float) -> bool:
            return 0 <= p <= 1

        if not map(check_prob, probs_ctrl) or not check_prob(sum(probs_ctrl)):
            raise ValueError(
                f"Invalid control probabilities for CZ Pauli channel (px_ctrl, py_ctrl, pz_ctrl): {probs_ctrl}"
            )

        probs_qarg = (self.px_qarg, self.py_qarg, self.pz_qarg)
        if not map(check_prob, probs_qarg) or not check_prob(sum(probs_qarg)):
            raise ValueError(
                f"Invalid probabilities for CZ Pauli channel (px_qarg, py_qarg, pz_qarg): {probs_qarg}"
            )


@statement(dialect=dialect)
class AtomLossChannel(ir.Statement):

    traits = frozenset({lowering.FromPythonCall()})

    prob: float = info.attribute(types.Float)
    qargs: ir.SSAValue = info.argument(ilist.IListType[QubitType])

    def check(self):
        if not 0 <= self.prob <= 1:
            raise ValueError(f"Invalid atom loss probability {self.prob}")
