"""
qubit.address method table for a few builtin dialects.
"""

from itertools import chain

from kirin import ir, interp
from kirin.analysis import ForwardFrame, const
from kirin.dialects import cf, py, scf, func, ilist

from .lattice import (
    Address,
    ConstResult,
    PartialIList,
    PartialTuple,
    PartialLambda,
)
from .analysis import AddressFrame, AddressAnalysis


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
class PyBinOp(interp.MethodTable):
    @interp.impl(py.Add)
    def add(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: py.Add,
    ):
        lhs = frame.get(stmt.lhs)
        rhs = frame.get(stmt.rhs)

        lhs_type, lhs_values = interp_.unpack_iterable(lhs)
        rhs_type, rhs_values = interp_.unpack_iterable(rhs)

        if lhs_type is None or rhs_type is None:
            return (Address.top(),)

        if lhs_type is not rhs_type:
            return (Address.bottom(),)

        return (lhs_type(tuple(chain(lhs_values, rhs_values))),)


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
class IListMethods(interp.MethodTable):
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
        fn = frame.get(stmt.fn)
        collection = frame.get(stmt.collection)
        collection_type, values = interp_.unpack_iterable(collection)

        if collection_type is None:
            return (Address.top(),)

        if collection_type is not PartialIList:
            return (Address.bottom(),)

        results = []
        for ele in values:
            ret = interp_.run_lattice(fn, (ele,), (), ())
            results.append(ret)

        if isinstance(stmt, ilist.Map):
            return (PartialIList(tuple(results)),)


@py.len.dialect.register(key="qubit.address")
class PyLen(interp.MethodTable):
    @interp.impl(py.Len)
    def len_(
        self, interp_: AddressAnalysis, frame: ForwardFrame[Address], stmt: py.Len
    ):
        obj = frame.get(stmt.value)
        _, values = interp_.unpack_iterable(obj)

        if values is None:
            return (Address.top(),)

        return (ConstResult(const.Value(len(values))),)


@py.indexing.dialect.register(key="qubit.address")
class PyIndexing(interp.MethodTable):
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

        typ, values = interp_.unpack_iterable(obj)
        if typ is None:
            return (Address.top(),)

        int_index = interp_.get_const_value(index, int)
        if int_index is not None:
            return (values[int_index],)

        slice_index = interp_.get_const_value(index, slice)
        if slice_index is not None:
            return (typ(values[slice_index]),)

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


# TODO: look for abstract method table for func.
@func.dialect.register(key="qubit.address")
class Func(interp.MethodTable):
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
        frame: AddressFrame,
        stmt: func.Invoke,
    ):
        call_frame, ret = interp_.call(
            stmt.callee.code,
            interp_.method_self(stmt.callee),
            *frame.get_values(stmt.inputs),
        )

        frame.collect_invoke_addresses(call_frame, stmt)

        return (ret,)

    @interp.impl(func.Lambda)
    def lambda_(
        self,
        inter_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.Lambda,
    ):
        arg_names = [
            arg.name or str(idx) for idx, arg in enumerate(stmt.body.blocks[0].args)
        ]
        return (
            PartialLambda(
                arg_names,
                stmt,
                frame.get_values(stmt.captured),
            ),
        )

    @interp.impl(func.Call)
    def call(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.Call,
    ):
        result = interp_.run_lattice(
            frame.get(stmt.callee),
            frame.get_values(stmt.inputs),
            stmt.keys,
            frame.get_values(stmt.kwargs),
        )
        return (result,)

    @interp.impl(func.GetField)
    def get_field(
        self,
        interp_: AddressAnalysis,
        frame: ForwardFrame[Address],
        stmt: func.GetField,
    ):
        self_mt = frame.get(stmt.obj)
        match self_mt:
            case PartialLambda(captured=captured):
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
class Scf(interp.MethodTable):
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
        frame: AddressFrame,
        stmt: scf.IfElse,
    ):
        address_cond = frame.get(stmt.cond)
        # run specific branch
        if isinstance(address_cond, ConstResult) and isinstance(
            const_cond := address_cond.result, const.Value
        ):
            body = stmt.then_body if const_cond.data else stmt.else_body
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                ret = interp_.frame_call_region(body_frame, stmt, body, address_cond)
                frame.collect_invoke_addresses(body_frame)
                # interp_.set_values(frame, body_frame.entries.keys(), body_frame.entries.values())
                return ret
        else:
            # run both branches
            with interp_.new_frame(stmt, has_parent_access=True) as then_frame:
                then_results = interp_.frame_call_region(
                    then_frame,
                    stmt,
                    stmt.then_body,
                    address_cond,
                )
                frame.set_values(then_frame.entries.keys(), then_frame.entries.values())
                frame.collect_invoke_addresses(then_frame)

            with interp_.new_frame(stmt, has_parent_access=True) as else_frame:
                else_results = interp_.frame_call_region(
                    else_frame,
                    stmt,
                    stmt.else_body,
                    address_cond,
                )
                frame.set_values(else_frame.entries.keys(), else_frame.entries.values())
                frame.collect_invoke_addresses(else_frame)
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
        iter_type, iterable = interp_.unpack_iterable(frame.get(stmt.iterable))

        if iter_type is None:
            return interp_.eval_fallback(frame, stmt)

        body_values = {}
        for value in iterable:
            with interp_.new_frame(stmt, has_parent_access=True) as body_frame:
                loop_vars = interp_.frame_call_region(
                    body_frame, stmt, stmt.body, value, *loop_vars
                )

            for ssa, val in body_frame.entries.items():
                body_values[ssa] = body_values.setdefault(ssa, val).join(val)

            if loop_vars is None:
                loop_vars = ()

            elif isinstance(loop_vars, interp.ReturnValue):
                frame.set_values(body_frame.entries.keys(), body_frame.entries.values())
                return loop_vars

        frame.set_values(body_values.keys(), body_values.values())
        return loop_vars
