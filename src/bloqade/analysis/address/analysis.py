from typing import TypeVar
from dataclasses import field

from kirin import ir, types, interp
from kirin.analysis import Forward, const
from kirin.analysis.forward import ForwardFrame

from .lattice import Joint, NotQubit, JointResult


class AddressAnalysis(Forward[Joint]):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.
    """

    keys = ["qubit.address"]
    _const_prop: const.Propagate
    lattice = Joint
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

    def to_joint_result(self, constant: const.Result):
        return JointResult(qubit=NotQubit(), constant=constant)

    def try_eval_const_prop(
        self,
        frame: ForwardFrame[Joint],
        stmt: ir.Statement,
        args: tuple[JointResult, ...],
    ) -> interp.StatementResult[Joint]:
        _frame = self._const_prop.initialize_frame(frame.code)
        _frame.set_values(stmt.args, tuple(x.constant for x in args))
        result = self._const_prop.eval_stmt(_frame, stmt)

        match result:
            case interp.ReturnValue(constant_ret):
                return interp.ReturnValue(self.to_joint_result(constant_ret))
            case interp.YieldValue(constant_values):
                return interp.YieldValue(
                    tuple(map(self.to_joint_result, constant_values))
                )
            case interp.Successor(block, block_args):
                return interp.Successor(block, *map(self.to_joint_result, block_args))
            case tuple():
                return tuple(map(self.to_joint_result, result))
            case _:
                return result

    def eval_stmt_fallback(self, frame: ForwardFrame[Joint], stmt: ir.Statement):
        args = frame.get_values(stmt.args)
        if types.is_tuple_of(args, JointResult) and all(
            isinstance(arg.qubit, NotQubit) for arg in args
        ):
            return self.try_eval_const_prop(frame, stmt, args)

        return tuple(Joint.top() for _ in stmt.results)

    def run_method(self, method: ir.Method, args: tuple[Joint, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        self_mt = JointResult(NotQubit(), constant=const.Value(method))
        return self.run_callable(method.code, (self_mt,) + args)
