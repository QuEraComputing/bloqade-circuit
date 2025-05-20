from typing import Tuple

from kirin import ir, types, lowering
from kirin.decl import info, statement
from kirin.dialects import ilist

from bloqade.types import QubitType

from ._dialect import dialect


@statement
class NativeNoiseStmt(ir.Statement):
    traits = frozenset({lowering.FromPythonCall()})

    @property
    def probabilities(self) -> Tuple[Tuple[float, ...], ...]:
        raise NotImplementedError(f"Override the method in {type(self).__name__}")

    def check(self):
        for probs in self.probabilities:
            self.check_probability(sum(probs))
            for p in probs:
                self.check_probability(p)

    def check_probability(self, p: float):
        if not 0 <= p <= 1:
            raise ValueError(
                f"Invalid noise probability encountered in {type(self).__name__}: {p}"
            )


@statement(dialect=dialect)
class PauliChannel(NativeNoiseStmt):
    px: float = info.attribute(types.Float)
    py: float = info.attribute(types.Float)
    pz: float = info.attribute(types.Float)
    qargs: ir.SSAValue = info.argument(ilist.IListType[QubitType])

    @property
    def probabilities(self) -> Tuple[Tuple[float, ...], ...]:
        return ((self.px, self.py, self.pz),)


NumQubits = types.TypeVar("NumQubits")


@statement(dialect=dialect)
class CZPauliChannel(NativeNoiseStmt):
    paired: bool = info.attribute(types.Bool)
    px_ctrl: float = info.attribute(types.Float)
    py_ctrl: float = info.attribute(types.Float)
    pz_ctrl: float = info.attribute(types.Float)
    px_qarg: float = info.attribute(types.Float)
    py_qarg: float = info.attribute(types.Float)
    pz_qarg: float = info.attribute(types.Float)
    ctrls: ir.SSAValue = info.argument(ilist.IListType[QubitType, NumQubits])
    qargs: ir.SSAValue = info.argument(ilist.IListType[QubitType, NumQubits])

    @property
    def probabilities(self) -> Tuple[Tuple[float, ...], ...]:
        return (
            (self.px_ctrl, self.py_ctrl, self.pz_ctrl),
            (self.px_qarg, self.py_qarg, self.pz_qarg),
        )


@statement(dialect=dialect)
class AtomLossChannel(NativeNoiseStmt):
    prob: float = info.attribute(types.Float)
    qargs: ir.SSAValue = info.argument(ilist.IListType[QubitType])

    @property
    def probabilities(self) -> Tuple[Tuple[float, ...], ...]:
        return ((self.prob,),)
