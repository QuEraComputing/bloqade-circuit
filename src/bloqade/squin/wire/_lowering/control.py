"""Carry allocation state through Kirin's structured Python control flow."""

import ast
from collections.abc import Sequence

from kirin import ir, types, lowering
from kirin.dialects import py, scf, ilist
from kirin.dialects.py.unpack import unpacking

from bloqade.analysis.indices import Iter, IndexExpr
from bloqade.analysis.indices.expr import loop_values
from bloqade.squin.emit.wire.values import contains_location

from .core import KEY, driver


def finish(state: lowering.State[ast.AST], values: Sequence[ir.SSAValue]) -> None:
    """Free region-local allocations and yield the continuing values."""
    frontend = driver(state)
    frame = frontend.frame(state)
    frame.free_local_allocations()
    frontend.done.update(frame.output.stmts)
    frontend.push(state, scf.Yield(*values))


def ordinary(state: lowering.State[ast.AST], value: ir.SSAValue) -> ir.SSAValue:
    """Resolve a classical expression to the value that its wire block defines."""
    frontend = driver(state)
    meaning = frontend.meaning(value)
    if isinstance(meaning, ir.SSAValue):
        return meaning
    return frontend.emitter.classical_value(frontend.frame(state), meaning)


@scf.dialect.register(key=KEY)
class ControlFlow(lowering.FromPythonAST):
    """Lower branches and loops with explicit allocation state in their results."""

    def lower_For(self, state: lowering.State[ast.AST], node: ast.For) -> None:
        """Capture referenced values and carry their updates between loop iterations."""
        if node.orelse:
            raise lowering.BuildError(
                "Structured wire loops do not support an else clause."
            )
        frontend = driver(state)
        iterable = state.lower(node.iter).expect_one()
        quantum = contains_location(frontend.meaning(iterable))
        if quantum:
            frame = frontend.frame(state)
            length = frontend.emitter.length_value(frame, frontend.meaning(iterable))
            frontend.done.update(state.current_frame.curr_block.stmts)
            frontend.sync(state, frame)
            stop = length
            zero = frontend.push(state, py.Constant(0)).results[0]
            one = frontend.push(state, py.Constant(1)).results[0]
            iterable_value = frontend.push(
                state, ilist.stmts.Range(zero, stop, one)
            ).results[0]
        else:
            iterable_value = ordinary(state, iterable)
        parent = state.current_frame
        names: list[str] = []

        def capture(body: lowering.Frame[ast.AST], value: ir.SSAValue) -> ir.SSAValue:
            """Capture a classical binding or retain a quantum location descriptor."""
            name = next(reversed(body.captures))
            meaning = frontend.meaning(value)
            if contains_location(meaning):
                return value
            names.append(name)
            return body.curr_block.args.append_from(ordinary(state, value).type, name)

        with state.frame(
            node.body, capture_callback=capture, finalize_next=False
        ) as body:
            index = body.curr_block.args.append_from(
                types.Int if quantum else types.Any
            )
            marker_body = ir.Block([scf.Yield()], argtypes=(types.Int,))
            marker = scf.For(iterable_value, ir.Region(marker_body))
            # The marker gives index proofs a loop identity before the body is complete.
            frontend.loop_markers.append(marker)
            frontend.emitter.indices.facts[index] = IndexExpr.of(
                Iter(marker, loop_values(iterable_value))
            )
            frontend.frame(state).entries[marker_body.args[0]] = index
            if quantum:
                item = body.push(py.GetItem(iterable, index))
                frontend.process(state, item)
                unpacking(
                    state, node.target, frontend.value(frontend.meaning(item.result))
                )
            else:
                unpacking(state, node.target, index)
            body.exhaust()
            for name, value in tuple(body.defs.items()):
                previous = parent.get_local(name)
                if previous is None:
                    continue
                before, after = frontend.meaning(previous), frontend.meaning(value)
                if contains_location(before) or contains_location(after):
                    if before != after:
                        raise lowering.BuildError(
                            "A loop must preserve the qubit location of each outer binding."
                        )
                elif name not in names:
                    names.append(name)
                    body.curr_block.args.append_from(
                        ordinary(state, previous).type, name
                    )
            outputs = tuple(ordinary(state, body.defs[name]) for name in names)
            finish(state, outputs)
        inputs = tuple(ordinary(state, parent.defs[name]) for name in names)
        made = frontend.push(state, scf.For(iterable_value, body.curr_region, *inputs))
        for name, value in zip(names, made.results, strict=True):
            value.name = name
            parent.defs[name] = value
        frontend.frame(state)

    def lower_If(self, state: lowering.State[ast.AST], node: ast.If) -> None:
        """Join classical bindings and allocation state from both branches."""
        self.branch(state, node.test, node.body, node.orelse)

    def branch(
        self,
        state: lowering.State[ast.AST],
        test: ast.expr,
        yes: Sequence[ast.stmt],
        no: Sequence[ast.stmt],
    ) -> None:
        """Lower both paths and expose names that have a value on each path."""
        frontend = driver(state)
        condition = ordinary(state, state.lower(test).expect_one())
        if condition.type != types.Bool:
            condition = frontend.push(
                state, py.Not(frontend.push(state, py.Not(condition)).results[0])
            ).results[0]
        parent = state.current_frame
        branches: list[lowering.Frame[ast.AST]] = []
        for statements in (yes, no):
            with state.frame(statements, finalize_next=False) as body:
                body.curr_block.args.append_from(types.Bool)
                body.exhaust()
                frontend.frame(state)
                branches.append(body)
        left, right = branches
        names = list(dict.fromkeys((*left.defs, *right.defs)))
        merged: list[str] = []
        aliases: dict[str, ir.SSAValue] = {}
        values: list[list[ir.SSAValue]] = [[], []]
        for name in names:
            lhs = left.defs.get(name, parent.get_local(name))
            rhs = right.defs.get(name, parent.get_local(name))
            if lhs is None or rhs is None:
                continue
            a, b = frontend.meaning(lhs), frontend.meaning(rhs)
            if contains_location(a) or contains_location(b):
                if a != b:
                    raise lowering.BuildError(
                        "Both branches must preserve the same qubit location for an outer binding."
                    )
                aliases[name] = lhs
            else:
                merged.append(name)
                for body, outputs, value in zip(
                    branches, values, (lhs, rhs), strict=True
                ):
                    state.push_frame(body)
                    try:
                        outputs.append(ordinary(state, value))
                    finally:
                        state.pop_frame(finalize_next=False)
        for body, outputs in zip(branches, values, strict=True):
            state.push_frame(body)
            try:
                finish(state, outputs)
            finally:
                state.pop_frame(finalize_next=False)
        made = frontend.push(
            state, scf.IfElse(condition, left.curr_region, right.curr_region)
        )
        for name, value in zip(merged, made.results, strict=True):
            value.name = name
            parent.defs[name] = value
        parent.defs.update(aliases)
        frontend.frame(state)

    def lower_IfExp(
        self, state: lowering.State[ast.AST], node: ast.IfExp
    ) -> ir.SSAValue:
        """Lower a conditional expression using the same ownership rules as a branch."""
        name = f"$expression{len(driver(state).done)}"
        yes = ast.copy_location(
            ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=node.body),
            node,
        )
        no = ast.copy_location(
            ast.Assign(targets=[ast.Name(id=name, ctx=ast.Store())], value=node.orelse),
            node,
        )
        self.branch(state, node.test, [yes], [no])
        return state.current_frame.defs.pop(name)


@py.boolop.dialect.register(key=KEY)
class BooleanExpressions(lowering.FromPythonAST):
    """Preserve Python operand selection and conditional evaluation."""

    def lower_BoolOp(
        self, state: lowering.State[ast.AST], node: ast.BoolOp
    ) -> ir.SSAValue:
        """Evaluate each later operand only on the path that needs its value."""
        value = state.lower(node.values[0]).expect_one()
        for expression in node.values[1:]:
            name = f"$boolean{len(driver(state).done)}"
            state.current_frame.defs[name] = value
            reference = ast.Name(id=name, ctx=ast.Load())
            yes, no = (
                (expression, reference)
                if isinstance(node.op, ast.And)
                else (reference, expression)
            )
            choice = ast.copy_location(
                ast.IfExp(test=reference, body=yes, orelse=no), node
            )
            value = state.lower(choice).expect_one()
            state.current_frame.defs.pop(name)
        return value
