from typing import TypeVar
from dataclasses import field

from kirin import ir, types, interp
from kirin.analysis import Forward, const
from kirin.dialects import func, ilist
from kirin.analysis.forward import ForwardFrame

from bloqade.types import QubitType

from .lattice import NotQubit, AnyAddress, JointLattice


def is_addresstype(typ: types.TypeAttribute):
    ret = (
        typ.is_subseteq(QubitType)
        or typ.is_subseteq(types.Tuple[types.Vararg(QubitType)])
        or typ.is_subseteq(ilist.IListType[QubitType, types.Any])
    )
    return ret


class AddressAnalysis(Forward[JointLattice]):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.
    """

    keys = ["qubit.address"]
    _const_prop: const.Propagate
    lattice = JointLattice
    next_address: int = field(init=False)

    def initialize(self):
        super().initialize()
        self.next_address: int = 0
        self._const_prop = const.Propagate(self.dialects)
        self._const_prop.initialize()
        return self

    @property
    def qubit_count(self) -> int:
        """Total number of qubits found by the analysis."""
        return self.next_address

    T = TypeVar("T")

    def try_eval_const_prop(
        self,
        frame: ForwardFrame[JointLattice],
        stmt: ir.Statement,
        values: tuple[JointLattice, ...],
    ):
        _frame = self._const_prop.initialize_frame(frame.code)
        _frame.set_values(stmt.args, tuple(x.constant for x in values))
        return self._const_prop.eval_stmt(_frame, stmt)

    def get_const_value(self, typ: type[T], value: ir.SSAValue) -> T:
        if isinstance(hint := value.hints.get("const"), const.Value):
            data = hint.data
            if isinstance(data, typ):
                return hint.data
            raise interp.InterpreterError(
                f"Expected constant value <type = {typ}>, got {data}"
            )
        raise interp.InterpreterError(
            f"Expected constant value <type = {typ}>, got {value}"
        )

    def eval_stmt_fallback(self, frame: ForwardFrame[JointLattice], stmt: ir.Statement):
        constants = self.try_eval_const_prop(frame, stmt, frame.get_values(stmt.args))
        match constants:
            case tuple():
                return tuple(
                    JointLattice(
                        (AnyAddress() if is_addresstype(result.type) else NotQubit()),
                        constant,
                    )
                    for result, constant in zip(stmt.results, constants)
                )
            case interp.ReturnValue(ret):
                if isinstance(stmt, func.Return):
                    address = (
                        AnyAddress() if is_addresstype(stmt.value.type) else NotQubit()
                    )
                else:
                    address = (
                        AnyAddress()
                    )  # Cannot determine the address type, defaulto to top.

                return interp.ReturnValue(JointLattice(address, ret))
            case interp.YieldValue(yields):
                return interp.YieldValue(
                    tuple(
                        JointLattice(
                            (
                                AnyAddress()
                                if is_addresstype(result.type)
                                else NotQubit()
                            ),
                            yielded,
                        )
                        for result, yielded in zip(stmt.results, yields)
                    )
                )
            case interp.Successor(block, block_args):
                return interp.Successor(
                    block,
                    *(
                        JointLattice(
                            (AnyAddress() if is_addresstype(arg.type) else NotQubit()),
                            arg,
                        )
                        for arg in block_args
                    ),
                )
            case None:
                return None
            case _:
                raise interp.InterpreterError(
                    "Unrecognized special value from const prop."
                )

    def run_method(self, method: ir.Method, args: tuple[JointLattice, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)
