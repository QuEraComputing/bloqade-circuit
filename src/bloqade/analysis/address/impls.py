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
    ConstResult,
    PartialIList,
    PartialTuple,
    PartialLambda,
    StaticContainer,
)
from .analysis import AddressAnalysis


class CallInterfaceMixin:
    def call_joint(
        self,
        interp_: AddressAnalysis,
        callee: Address,
        inputs: tuple[Address, ...],
        kwargs: tuple[str, ...],
    ) -> Address:
        match callee:
            case PartialLambda(code=code, argnames=argnames):
                _, ret = interp_.run_callable(
                    code, (callee,) + interp_.permute_values(argnames, inputs, kwargs)
                )
                return ret
            case ConstResult(constant=const.Value(data=ir.Method() as method)):
                _, ret = interp_.run_method(
                    method,
                    interp_.permute_values(method.arg_names, inputs, kwargs),
                )
                return ret
            case _:
                return Address.top()


class GetValuesMixin:
    def get_values(self, collection: Address):
        def from_constant(constant: const.Result) -> Address:
            return ConstResult(constant)

        def from_literal(literal: Any) -> Address:
            return ConstResult(const.Value(literal))

        match collection:
            case PartialIList(data) | PartialTuple(data):
                return data
            case ConstResult(const.Value(data)) if isinstance(data, Iterable):
                return tuple(map(from_literal, data))
            case ConstResult(const.PartialTuple(data)):

                return tuple(map(from_constant, data))


@py.constant.dialect.register(key="qubit.address")
class PyConstant(interp.MethodTable):
    @interp.impl(py.Constant)
    def constant(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: py.Constant,
    ):
        return (ConstResult(const.Value(stmt.value.unwrap())),)


@py.binop.dialect.register(key="qubit.address")
class PyBinOp(interp.MethodTable, GetValuesMixin):
    @interp.impl(py.Add)
    def add(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: py.Add,
    ):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        match lhs, rhs:
            case PartialTuple(lhs_data), PartialTuple(rhs_data):
                return (PartialTuple(lhs_data + rhs_data),)
            case PartialIList(lhs_data), PartialIList(rhs_data):
                return (PartialIList(lhs_data + rhs_data),)

        return interp_.eval_stmt_fallback(frame, stmt)


@py.tuple.dialect.register(key="qubit.address")
class PyTuple(interp.MethodTable):
    @interp.impl(py.tuple.New)
    def new_tuple(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: py.tuple.New,
    ):
        return (PartialTuple(frame.get_values(stmt.args)),)


@ilist.dialect.register(key="qubit.address")
class IList(interp.MethodTable, CallInterfaceMixin, GetValuesMixin):
    @interp.impl(ilist.New)
    def new_ilist(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: ilist.New,
    ):
        return (PartialIList(frame.get_values(stmt.args)),)

    @interp.impl(ilist.ForEach)
    @interp.impl(ilist.Map)
    def map_(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: ilist.Map | ilist.ForEach,
    ):
        results = []
        fn = frame.get(stmt.fn)
        collection = frame.get(stmt.collection)
        iterable = self.get_values(collection)

        if iterable is None:
            return (Address.top(),)

        results = []
        for ele in iterable:
            results.append(self.call_joint(interp_, fn, (ele,), ()))

        if isinstance(stmt, ilist.Map):
            return (PartialIList(tuple(results)),)


@py.indexing.dialect.register(key="qubit.address")
class PyIndexing(interp.MethodTable, GetValuesMixin):
    @interp.impl(py.GetItem)
    def getitem(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: py.GetItem,
    ):
        # determine if the index is an int constant
        # or a slice
        obj = frame.get(stmt.obj)
        index = frame.get(stmt.index)

        values = self.get_values(obj)

        if not isinstance(obj, StaticContainer):
            return interp_.eval_stmt_fallback(frame, stmt)

        if values is None:
            return (Address.top(),)

        match index:
            case ConstResult(const.Value(int() as idx)):
                return (values[idx],)
            case ConstResult(const.Value(slice() as idx)):
                return (obj.new(values[idx]),)

        return (Address.top(),)


@py.assign.dialect.register(key="qubit.address")
class PyAssign(interp.MethodTable):
    @interp.impl(py.Alias)
    def alias(
        self,
        interp: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: py.Alias,
    ):
        return (frame.get(stmt.value),)


@func.dialect.register(key="qubit.address")
class Func(interp.MethodTable, CallInterfaceMixin):
    @interp.impl(func.Return)
    def return_(
        self,
        _: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.Return,
    ):
        return interp.ReturnValue(frame.get(stmt.value))

    # TODO: replace with the generic implementation
    @interp.impl(func.Invoke)
    def invoke(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
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

    @interp.impl(func.Lambda)
    def lambda_(
        self,
        inter_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.Lambda,
    ):
        captured = frame.get_values(stmt.captured)
        arg_names = [
            arg.name or str(idx) for idx, arg in enumerate(stmt.body.blocks[0].args)
        ]

        return (
            PartialLambda(
                arg_names,
                stmt,
                tuple(each for each in captured),
            ),
        )

    @interp.impl(func.Call)
    def call(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.Call,
    ):
        return (
            self.call_joint(
                interp_,
                frame.get(stmt.callee),
                frame.get_values(stmt.inputs),
                stmt.kwargs,
            ),
        )

    @interp.impl(func.GetField)
    def get_field(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.GetField,
    ):
        self_mt = frame.get(stmt.obj)
        match self_mt:
            case PartialLambda(captured):
                return (captured[stmt.field],)
            case ConstResult(const.Value(ir.Method() as mt)):
                return (ConstResult(const.Value(mt.fields[stmt.field])),)

        return (Address.top(),)


@cf.dialect.register(key="qubit.address")
class Cf(interp.MethodTable):

    @interp.impl(cf.Branch)
    def branch(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: cf.Branch,
    ):
        frame.worklist.append(
            interp.Successor(stmt.successor, *frame.get_values(stmt.arguments))
        )
        return ()

    @interp.impl(cf.ConditionalBranch)
    def conditional_branch(
        self,
        interp_: const.Propagate,
        frame: ForwardFrame[Address],
        stmt: cf.ConditionalBranch,
    ):
        address_cond = frame.get(stmt.cond)

        if isinstance(address_cond, ConstResult) and isinstance(
            cond := address_cond.result, const.Value
        ):
            else_successor = interp.Successor(
                stmt.else_successor, *frame.get_values(stmt.else_arguments)
            )
            then_successor = interp.Successor(
                stmt.then_successor, *frame.get_values(stmt.then_arguments)
            )
            if cond.data:
                frame.worklist.append(then_successor)
            else:
                frame.worklist.append(else_successor)
        else:
            frame.entries[stmt.cond] = ConstResult(const.Value(True))
            then_successor = interp.Successor(
                stmt.then_successor, *frame.get_values(stmt.then_arguments)
            )
            frame.worklist.append(then_successor)

            frame.entries[stmt.cond] = ConstResult(const.Value(False))
            else_successor = interp.Successor(
                stmt.else_successor, *frame.get_values(stmt.else_arguments)
            )
            frame.worklist.append(else_successor)

            frame.entries[stmt.cond] = address_cond
        return ()


@scf.dialect.register(key="qubit.address")
class Scf(interp.MethodTable, GetValuesMixin):
    @interp.impl(scf.Yield)
    def yield_(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: scf.Yield,
    ):
        return interp.YieldValue(frame.get_values(stmt.values))

    @interp.impl(scf.IfElse)
    def ifelse(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: scf.IfElse,
    ):
        address_cond = frame.get(stmt.cond)

        # run specific branch
        if isinstance(address_cond, ConstResult) and isinstance(
            const_cond := address_cond.result, const.Value
        ):
            body = stmt.then_body if const_cond.data else stmt.else_body
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                ret = interp_.run_ssacfg_region(body_frame, body, (address_cond,))
                frame.entries.update(body_frame.entries)
                return ret
        else:
            # run both branches
            with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
                then_results = interp_.run_ssacfg_region(
                    then_frame, stmt.then_body, (address_cond,)
                )

            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                else_results = interp_.run_ssacfg_region(
                    else_frame, stmt.else_body, (address_cond,)
                )

            frame.entries.update(then_frame.entries)
            frame.entries.update(else_frame.entries)
            # TODO: pick the non-return value
            if isinstance(then_results, interp.ReturnValue) and isinstance(
                else_results, interp.ReturnValue
            ):
                return interp.ReturnValue(then_results.value.join(else_results.value))
            elif isinstance(then_results, interp.ReturnValue):
                ret = else_results
            elif isinstance(else_results, interp.ReturnValue):
                ret = then_results
            else:
                ret = interp_.join_results(then_results, else_results)

            return ret

    @interp.impl(scf.For)
    def for_loop(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: scf.For,
    ):
        loop_vars = frame.get_values(stmt.initializers)
        iterable = self.get_values(frame.get(stmt.iterable))
        if iterable is None:
            return interp_.eval_stmt_fallback(frame, stmt)

        for value in iterable:
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                loop_vars = interp_.run_ssacfg_region(
                    body_frame, stmt.body, (value,) + loop_vars
                )
            if loop_vars is None:
                loop_vars = ()

            elif isinstance(loop_vars, interp.ReturnValue):
                return loop_vars

        return loop_vars
