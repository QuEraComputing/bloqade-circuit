from typing import Any, Type, TypeVar
from dataclasses import field

from kirin import ir, types, interp
from kirin.analysis import Forward, const
from kirin.dialects.ilist import IList
from kirin.analysis.forward import ForwardFrame
from kirin.analysis.const.lattice import PartialLambda

from .lattice import Address, AddressReg, ConstResult, PartialIList, PartialTuple


class AddressAnalysis(Forward[Address]):
    """
    This analysis pass can be used to track the global addresses of qubits and wires.
    """

    keys = ["qubit.address"]
    _const_prop: const.Propagate
    lattice = Address
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

    def to_address(self, result: const.Result):
        return ConstResult(result)

    def try_eval_const_prop(
        self,
        frame: ForwardFrame[Address],
        stmt: ir.Statement,
        args: tuple[ConstResult, ...],
    ) -> interp.StatementResult[Address]:
        _frame = self._const_prop.initialize_frame(frame.code)
        _frame.set_values(stmt.args, tuple(x.result for x in args))
        result = self._const_prop.eval_stmt(_frame, stmt)

        match result:
            case interp.ReturnValue(constant_ret):
                return interp.ReturnValue(self.to_address(constant_ret))
            case interp.YieldValue(constant_values):
                return interp.YieldValue(tuple(map(self.to_address, constant_values)))
            case interp.Successor(block, block_args):
                return interp.Successor(block, *map(self.to_address, block_args))
            case tuple():
                return tuple(map(self.to_address, result))
            case _:
                return result

    def unpack_iterable(self, iterable: Address):
        """Extract the values of a container lattice element.

        Args:
            iterable: The lattice element representing a container.

        Returns:
            A tuple of the container type and the contained values.

        """

        def from_constant(constant: const.Result) -> Address:
            return ConstResult(constant)

        def from_literal(literal: Any) -> Address:
            return ConstResult(const.Value(literal))

        match iterable:
            case PartialIList(data):
                return PartialIList, data
            case PartialTuple(data):
                return PartialTuple, data
            case AddressReg():
                return PartialIList, iterable.qubits
            case ConstResult(const.Value(IList() as data)):
                return PartialIList, tuple(map(from_literal, data))
            case ConstResult(const.Value(tuple() as data)):
                return PartialTuple, tuple(map(from_literal, data))
            case ConstResult(const.PartialTuple(data)):
                return PartialTuple, tuple(map(from_constant, data))
            case _:
                return None, ()

    def run_lattice(
        self,
        callee: Address,
        inputs: tuple[Address, ...],
        kwargs: tuple[str, ...],
    ) -> Address:
        """Run a callable lattice element with the given inputs and keyword arguments.

        Args:
            callee (Address): The lattice element representing the callable.
            inputs (tuple[Address, ...]): The input lattice elements.
            kwargs (tuple[str, ...]): The keyword argument names.

        Returns:
            Address: The resulting lattice element after invoking the callable.

        """

        match callee:
            case PartialLambda(code=code, argnames=argnames):
                _, ret = self.run_callable(
                    code, (callee,) + self.permute_values(argnames, inputs, kwargs)
                )
                return ret
            case ConstResult(const.Value(ir.Method() as method)):
                _, ret = self.run_method(
                    method,
                    self.permute_values(method.arg_names, inputs, kwargs),
                )
                return ret
            case _:
                return Address.top()

    def get_const_value(self, addr: Address, typ: Type[T]) -> T | None:
        if not isinstance(addr, ConstResult):
            return None

        if not isinstance(result := addr.result, const.Value):
            return None

        if not isinstance(value := result.data, typ):
            return None

        return value

    def eval_stmt_fallback(self, frame: ForwardFrame[Address], stmt: ir.Statement):
        args = frame.get_values(stmt.args)
        if types.is_tuple_of(args, ConstResult):
            return self.try_eval_const_prop(frame, stmt, args)

        return tuple(Address.from_type(result.type) for result in stmt.results)

    def run_method(self, method: ir.Method, args: tuple[Address, ...]):
        # NOTE: we do not support dynamic calls here, thus no need to propagate method object
        self_mt = ConstResult(const.Value(method))
        return self.run_callable(method.code, (self_mt,) + args)
