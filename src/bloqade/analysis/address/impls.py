"""
qubit.address method table for a few builtin dialects.
"""

from typing import Any
from collections.abc import Iterable

from kirin import ir, interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import cf, py, scf, func, ilist

from .lattice import (
    Address,
    NotQubit,
    AnyAddress,
    AddressQubit,
    AddressTuple,
    JointLattice,
)
from .analysis import AddressAnalysis


class GetIterableMixin:
    def get_iterable(self, iterable_lattice: JointLattice):
        def literal_to_joint(literal: Any):
            return JointLattice(NotQubit(), const.Value(literal))

        def address_to_joint(address: Address):
            return JointLattice(address, const.Unknown())

        def address_literal_to_joint(address: Address, literal: Any):
            return JointLattice(address, const.Value(literal))

        match iterable_lattice:
            case JointLattice(NotQubit(), const.Value(iterable)) if isinstance(
                iterable, Iterable
            ):
                return tuple(map(literal_to_joint, iterable))
            case JointLattice(NotQubit(), const.PartialTuple(data)):
                return tuple(map(literal_to_joint, data))
            case JointLattice(AddressTuple(data), const.Value(iterable)) if isinstance(
                iterable, Iterable
            ):
                return tuple(map(address_literal_to_joint, data, iterable))
            case JointLattice(
                AddressTuple(address_data), const.PartialTuple(data=constant_data)
            ):
                return tuple(map(JointLattice, address_data, constant_data))
            case JointLattice(AddressTuple(data), _):
                return tuple(map(address_to_joint, data))
            case _:
                return None


@py.binop.dialect.register(key="qubit.address")
class PyBinOp(interp.MethodTable):

    @interp.impl(py.Add)
    def add(
        self, interp_: AddressAnalysis, frame: ForwardFrame[JointLattice], stmt: py.Add
    ):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        lhs_addr = lhs.address
        rhs_addr = rhs.address

        if isinstance(lhs_addr, AddressTuple) and isinstance(rhs_addr, AddressTuple):
            address = AddressTuple(data=lhs_addr.data + rhs_addr.data)
        else:
            address = NotQubit()

        constants = interp_.try_eval_const_prop(frame, stmt, (lhs, rhs))
        assert (
            isinstance(constants, tuple) and len(constants) == 1
        ), "Unexpected result from const prop in PyBinOp.add"

        return (JointLattice(address=address, constant=constants[0]),)


@py.tuple.dialect.register(key="qubit.address")
class PyTuple(interp.MethodTable):
    @interp.impl(py.tuple.New)
    def new_tuple(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: py.tuple.New,
    ):
        args = frame.get_values(stmt.args)
        address = AddressTuple(tuple(arg.address for arg in args))
        constant = const.PartialTuple(tuple(arg.constant for arg in args))

        return (JointLattice(address=address, constant=constant),)


@ilist.dialect.register(key="qubit.address")
class IList(interp.MethodTable, GetIterableMixin):
    @interp.impl(ilist.New)
    def new_ilist(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: ilist.New,
    ):
        args = frame.get_values(stmt.args)
        address = AddressTuple(tuple(arg.address for arg in args))
        constant = const.Unknown()
        return (JointLattice(address=address, constant=constant),)

    def run_callable(
        self,
        interp_: AddressAnalysis,
        callee: const.Result,
        args: tuple[JointLattice, ...],
    ):
        match callee:
            case const.Value(data=method) if isinstance(method, ir.Method):
                _, ret = interp_.run_method(
                    method,
                    interp_.permute_values(method.arg_names, args, ()),
                )
                return ret
            case const.PartialLambda(code=code):
                _, ret = interp_.run_callable(
                    code,
                    (JointLattice(NotQubit(), callee),)
                    + interp_.permute_values(callee.argnames, args, ()),
                )
                return ret

        return JointLattice(AnyAddress(), const.Unknown())

    @interp.impl(ilist.Map)
    def map_(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: ilist.Map,
    ):

        fn_lattice = frame.get(stmt.fn)
        assert isinstance(
            fn_lattice.address, NotQubit
        ), "Function should not be an address type"

        collection_lattice = frame.get(stmt.collection)
        collection = self.get_iterable(collection_lattice)

        fn = fn_lattice.constant

        if collection is None or isinstance(fn, const.Unknown):
            return interp_.eval_stmt_fallback(frame, stmt)

        address_values = []
        constant_values = []
        for item in collection:
            res = self.run_callable(interp_, fn, (item,))
            address_values.append(res.address)
            constant_values.append(res.constant)
        address = AddressTuple(tuple(address_values))

        if any(not isinstance(constant, const.Value) for constant in constant_values):
            constant = const.Unknown()
        else:
            constant = const.Value(
                ilist.IList(tuple(constant.data for constant in constant_values))
            )

        return (JointLattice(address=address, constant=constant),)


@py.list.dialect.register(key="qubit.address")
class PyList(interp.MethodTable):
    @interp.impl(py.list.New)
    def new_ilist(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: py.list.New,
    ):
        args = frame.get_values(stmt.args)
        address = AddressTuple(tuple(arg.address for arg in args))
        constant = const.Unknown()

        return (JointLattice(address=address, constant=constant),)


@py.indexing.dialect.register(key="qubit.address")
class PyIndexing(interp.MethodTable):
    @interp.impl(py.GetItem)
    def getitem(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: py.GetItem,
    ):

        # determine if the index is an int constant
        # or a slice
        obj = frame.get(stmt.obj)
        index = frame.get(stmt.index)
        assert isinstance(
            index.address, NotQubit
        ), "Index should not be an address type"

        constant = interp_.try_eval_const_prop(frame, stmt, (obj, index))
        assert (
            isinstance(constant, tuple) and len(constant) == 1
        ), "Unexpected result from const prop in PyIndexing.getitem"

        match (obj.address, index.constant):
            case (NotQubit(), _):
                address = NotQubit()
            case (AddressTuple(data=data), const.Value(data=int() as idx)):
                address = data[idx]
            case (AddressTuple(data=data), const.Value(data=slice() as idx)):
                address = AddressTuple(data=data[idx])
            case (AddressTuple(data=data), _):
                address = AnyAddress()
            case (AnyAddress(), _):
                address = AnyAddress()
            case (AddressQubit(), _):
                address = NotQubit()
            case _:
                raise InterruptedError("Unreachable code in PyIndexing.getitem")

        return (JointLattice(address, constant[0]),)


@py.assign.dialect.register(key="qubit.address")
class PyAssign(interp.MethodTable):
    @interp.impl(py.Alias)
    def alias(
        self, interp: AddressAnalysis, frame: ForwardFrame[JointLattice], stmt: py.Alias
    ):
        return (frame.get(stmt.value),)


@func.dialect.register(key="qubit.address")
class Func(interp.MethodTable):
    @interp.impl(func.Return)
    def return_(
        self, _: AddressAnalysis, frame: ForwardFrame[JointLattice], stmt: func.Return
    ):
        return interp.ReturnValue(frame.get(stmt.value))

    # TODO: replace with the generic implementation
    @interp.impl(func.Invoke)
    def invoke(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: func.Invoke,
    ):
        args = interp_.permute_values(
            stmt.callee.arg_names, frame.get_values(stmt.inputs), stmt.kwargs
        )
        _, ret = interp_.run_method(
            stmt.callee,
            args,
        )
        return (ret,)

    # TODO: support lambda?


@cf.dialect.register(key="qubit.address")
class Cf(cf.typeinfer.TypeInfer):
    # NOTE: cf just re-use the type infer method table
    # it's the same process as type infer.
    pass


@scf.dialect.register(key="qubit.address")
class Scf(scf.absint.Methods, GetIterableMixin):
    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[JointLattice],
        stmt: scf.For,
    ):
        iterable_lattice = frame.get(stmt.iterable)
        loop_vars = frame.get_values(stmt.initializers)
        iterable = self.get_iterable(iterable_lattice)

        # case where no qubits participate in the loop
        if (
            isinstance(iterable_lattice.address, NotQubit)
            and all(isinstance(lv.address, NotQubit) for lv in loop_vars)
            or iterable is None
        ):
            return interp_.eval_stmt_fallback(frame, stmt)

        loop_vars = frame.get_values(stmt.initializers)
        for value in iterable:
            print(value, loop_vars)
            loop_vars = interp_.run_ssacfg_region(
                frame, stmt.body, (value,) + loop_vars
            )

            if loop_vars is None:
                loop_vars = ()
            elif isinstance(loop_vars, interp.ReturnValue):
                return loop_vars

            interp_.set_values(frame, stmt.initializers, loop_vars)

        return frame.get_values(stmt.initializers)
