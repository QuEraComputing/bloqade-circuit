"""
qubit.address method table for a few builtin dialects.
"""

import typing
from typing import Any
from collections.abc import Iterable

from kirin import ir, interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import cf, py, scf, func, ilist

from . import lattice
from .analysis import AddressAnalysis


class CallInterfaceMixin:
    def call_joint(
        self,
        interp_: AddressAnalysis,
        callee: lattice.Joint,
        inputs: tuple[lattice.Joint, ...],
        kwargs: tuple[str, ...],
    ) -> lattice.Joint:
        match callee:
            case lattice.JointMethod(code=code, argnames=argnames):
                _, ret = interp_.run_callable(
                    code, (callee,) + interp_.permute_values(argnames, inputs, kwargs)
                )
                return ret
            case lattice.JointResult(constant=const.Value(data=ir.Method() as method)):
                _, ret = interp_.run_method(
                    method,
                    interp_.permute_values(method.arg_names, inputs, kwargs),
                )
                return ret
            case _:
                return lattice.Joint.top()


class GetValuesMixin:
    def get_values(self, collection: lattice.Joint):
        def from_constant(constant: const.Result) -> lattice.Joint:
            return lattice.JointResult(lattice.NotQubit(), constant)

        def from_literal(literal: Any) -> lattice.Joint:
            return lattice.JointResult(lattice.NotQubit(), const.Value(literal))

        match collection:
            case lattice.JointIList(data) | lattice.JointTuple(data):
                return data
            case lattice.JointResult(
                qubit=lattice.NotQubit(), constant=const.PartialTuple as constants
            ):
                return tuple(map(from_constant, constants.data))
            case lattice.JointResult(
                qubit=lattice.NotQubit(), constant=const.Value(data)
            ) if isinstance(data, Iterable):
                return tuple(map(from_literal, data))


@py.constant.dialect.register(key="qubit.address")
class PyConstant(interp.MethodTable):
    @interp.impl(py.Constant)
    def constant(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: py.Constant,
    ):
        return (
            lattice.JointResult(lattice.NotQubit(), const.Value(stmt.value.unwrap())),
        )


@py.binop.dialect.register(key="qubit.address")
class PyBinOp(interp.MethodTable, GetValuesMixin):
    @interp.impl(py.Add)
    def add(
        self, interp_: AddressAnalysis, frame: ForwardFrame[lattice.Joint], stmt: py.Add
    ):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)
        match lhs, rhs:
            case lattice.JointTuple(lhs_data), lattice.JointTuple(rhs_data):
                return (lattice.JointTuple(lhs_data + rhs_data),)
            case lattice.JointIList(lhs_data), lattice.JointIList(rhs_data):
                return (lattice.JointIList(lhs_data + rhs_data),)

        lhs_constant = lhs.get_constant()
        rhs_constant = rhs.get_constant()
        print(lhs, lhs_constant)

        match lhs, rhs_constant:
            case lattice.JointIList(), const.Value(ilist.IList() as lst) if (
                len(lst) == 0
            ):
                return (lhs,)
            case lattice.JointTuple(), const.Value(tuple() as tup) if len(tup) == 0:
                return (lhs,)

        match lhs_constant, rhs:
            case const.Value(ilist.IList() as lst), lattice.JointIList() if (
                len(lst) == 0
            ):
                return (rhs,)
            case const.Value(tuple() as tup), lattice.JointTuple() if len(tup) == 0:
                return (rhs,)

        return interp_.eval_stmt_fallback(frame, stmt)


@py.tuple.dialect.register(key="qubit.address")
class PyTuple(interp.MethodTable):
    @interp.impl(py.tuple.New)
    def new_tuple(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: py.tuple.New,
    ):
        return (lattice.JointTuple(frame.get_values(stmt.args)),)


@ilist.dialect.register(key="qubit.address")
class IList(interp.MethodTable, CallInterfaceMixin, GetValuesMixin):
    @interp.impl(ilist.New)
    def new_ilist(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: ilist.New,
    ):
        return (lattice.JointIList(frame.get_values(stmt.args)),)

    @interp.impl(ilist.ForEach)
    @interp.impl(ilist.Map)
    def map_(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: ilist.Map | ilist.ForEach,
    ):
        results = []
        fn = frame.get(stmt.fn)
        collection = frame.get(stmt.collection)
        iterable = self.get_values(collection)

        if iterable is None:
            return (lattice.Joint.top(),)

        results = []
        for ele in iterable:
            results.append(self.call_joint(interp_, fn, (ele,), ()))

        if isinstance(stmt, ilist.Map):
            return (lattice.JointIList(tuple(results)),)


@py.indexing.dialect.register(key="qubit.address")
class PyIndexing(interp.MethodTable):
    @interp.impl(py.GetItem)
    def getitem(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: py.GetItem,
    ):
        # determine if the index is an int constant
        # or a slice
        obj = frame.get(stmt.obj)
        index = frame.get(stmt.index)

        if not (
            isinstance(obj, lattice.JointStaticContainer)
            and isinstance(index, lattice.JointResult)
        ):
            return interp_.eval_stmt_fallback(frame, stmt)

        match index:
            case lattice.JointResult(lattice.NotQubit(), const.Value(int() as idx)):
                return (obj.data[idx],)
            case lattice.JointResult(lattice.NotQubit(), const.Value(slice() as idx)):
                return (obj.new(obj.data[idx]),)

        return (lattice.Joint.top(),)


@py.assign.dialect.register(key="qubit.address")
class PyAssign(interp.MethodTable):
    @interp.impl(py.Alias)
    def alias(
        self,
        interp: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: py.Alias,
    ):
        return (frame.get(stmt.value),)


@func.dialect.register(key="qubit.address")
class Func(interp.MethodTable, CallInterfaceMixin):
    @interp.impl(func.Return)
    def return_(
        self, _: AddressAnalysis, frame: ForwardFrame[lattice.Joint], stmt: func.Return
    ):
        return interp.ReturnValue(frame.get(stmt.value))

    # TODO: replace with the generic implementation
    @interp.impl(func.Invoke)
    def invoke(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
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
        frame: ForwardFrame[lattice.Joint],
        stmt: func.Lambda,
    ):
        captured = frame.get_values(stmt.captured)
        arg_names = [
            arg.name or str(idx) for idx, arg in enumerate(stmt.body.blocks[0].args)
        ]

        return (
            lattice.JointMethod(
                arg_names,
                stmt,
                tuple(each for each in captured),
            ),
        )

    @interp.impl(func.Call)
    def call(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
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
        frame: ForwardFrame[lattice.Joint],
        stmt: func.GetField,
    ):
        self_mt = frame.get(stmt.obj)
        if isinstance(self_mt, lattice.JointMethod):
            return (self_mt.captured[stmt.field],)

        self_constant = self_mt.get_constant()

        if not isinstance(self_constant, const.Value):
            return (lattice.Joint.top(),)

        mt = typing.cast(ir.Method, self_constant.data)

        value = mt.fields[stmt.field]

        return (
            lattice.JointResult(
                lattice.NotQubit(),
                const.Value(value),
            ),
        )


@cf.dialect.register(key="qubit.address")
class Cf(interp.MethodTable):

    @interp.impl(cf.Branch)
    def branch(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
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
        frame: ForwardFrame[lattice.Joint],
        stmt: cf.ConditionalBranch,
    ):
        joint_cond = frame.get(stmt.cond)
        cond = joint_cond.get_constant()

        if isinstance(cond, const.Value):
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
            frame.entries[stmt.cond] = lattice.JointResult(constant=const.Value(True))
            then_successor = interp.Successor(
                stmt.then_successor, *frame.get_values(stmt.then_arguments)
            )
            frame.worklist.append(then_successor)

            frame.entries[stmt.cond] = lattice.JointResult(constant=const.Value(False))
            else_successor = interp.Successor(
                stmt.else_successor, *frame.get_values(stmt.else_arguments)
            )
            frame.worklist.append(else_successor)

            frame.entries[stmt.cond] = joint_cond
        return ()


@scf.dialect.register(key="qubit.address")
class Scf(interp.MethodTable, GetValuesMixin):
    @interp.impl(scf.Yield)
    def yield_(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: scf.Yield,
    ):
        return interp.YieldValue(frame.get_values(stmt.values))

    @interp.impl(scf.IfElse)
    def ifelse(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[lattice.Joint],
        stmt: scf.IfElse,
    ):
        joint_cond = frame.get(stmt.cond)
        const_cond = joint_cond.get_constant()
        # run specific branch
        if isinstance(const_cond, const.Value):
            body = stmt.then_body if const_cond.data else stmt.else_body
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                ret = interp_.run_ssacfg_region(body_frame, body, (joint_cond,))
                frame.entries.update(body_frame.entries)
                return ret
        else:
            # run both branches
            with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
                then_results = interp_.run_ssacfg_region(
                    then_frame, stmt.then_body, (joint_cond,)
                )

            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                else_results = interp_.run_ssacfg_region(
                    else_frame, stmt.else_body, (joint_cond,)
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
        frame: ForwardFrame[lattice.Joint],
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
