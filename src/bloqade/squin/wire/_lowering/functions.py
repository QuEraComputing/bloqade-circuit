"""Lower Python function boundaries with explicit quantum inputs and outputs."""

import ast

from kirin import ir, types, lowering
from kirin.dialects import func
from kirin.dialects.lowering import func as func_lowering

from bloqade.analysis.indices import IndexExpr
from bloqade.squin.wire.types import WireType
from bloqade.squin.emit.wire.values import Qubit, Register, contains_location
from bloqade.squin.emit.wire.functions import emit_return
from bloqade.squin.rewrite.wire.signature import (
    quantum_type,
    parameter_type,
    register_shape,
)

from .core import KEY, driver


@func_lowering.dialect.register(key=KEY)
class Functions(func_lowering.Lowering):
    """Build wire signatures and free allocations before the final return."""

    def lower_FunctionDef(
        self, state: lowering.State[ast.AST], node: ast.FunctionDef
    ) -> None:
        """Lower a function body with classical values and quantum locations in scope."""
        if state.current_frame.parent is not None:
            raise lowering.BuildError(
                "Wire lowering requires helper functions at module scope."
            )
        self.assert_simple_arguments(node.args)
        if node.args.defaults or node.args.vararg or node.args.kwarg:
            raise lowering.BuildError("Wire kernels require explicit fixed arguments.")
        frontend = driver(state)
        frontend.input_types = tuple(
            self.get_hint(state, arg.annotation) for arg in node.args.args
        )
        frontend.return_type = self.get_hint(state, node.returns)
        inputs = tuple(parameter_type(typ) for typ in frontend.input_types)
        block = ir.Block(argtypes=(types.Any, *inputs))
        with state.frame(node.body, entr_block=block, finalize_next=False) as body:
            body.defs[node.name] = block.args[0]
            frame = frontend.frame(state)
            for arg, source_type, value in zip(
                node.args.args, frontend.input_types, block.args[1:], strict=True
            ):
                value.name = arg.arg
                if (linear := quantum_type(source_type)) is None:
                    binding = value
                else:
                    if linear == WireType:
                        location = Qubit(value)
                    else:
                        outer, *inner = register_shape(source_type)
                        location = Register(
                            value,
                            None if outer is None else IndexExpr(outer),
                            tuple(inner),
                        )
                    frontend.parameters.append(location)
                    frame.own(location, local=False)
                    binding = frontend.value(location)
                body.defs[arg.arg] = binding
                frame.entries[value] = value
            frontend.sync(state, frame)
            body.exhaust()
            if not isinstance(block.last_stmt, func.Return):
                self.lower_Return(
                    state, ast.copy_location(ast.Return(value=None), node)
                )
        signature = func.Signature(inputs, types.Any)
        block.args[0].type = types.MethodType[list(inputs), types.Any]
        frontend.push(
            state,
            func.Function(
                sym_name=node.name,
                slots=tuple(arg.arg for arg in node.args.args),
                signature=signature,
                body=body.curr_region,
            ),
        )

    def lower_Return(self, state: lowering.State[ast.AST], node: ast.Return) -> None:
        """Return classical results and updated quantum parameters after local cleanup."""
        if (
            state.current_frame.parent is None
            or state.current_frame.parent.parent is not None
        ):
            raise lowering.BuildError("Wire lowering requires a function-level return.")
        if state.current_frame.stream:
            raise lowering.BuildError(
                "A wire function must end at its return statement."
            )
        frontend = driver(state)
        value = (
            frontend.meaning(state.lower(node.value).expect_one())
            if node.value is not None
            else None
        )
        if contains_location(value):
            raise lowering.BuildError(
                "A wire function cannot return quantum values. Pass qubits through its parameters."
            )
        frame = frontend.frame(state)
        if value is None or (
            isinstance(value, ir.SSAValue) and value.type == types.NoneType
        ):
            ordinary = ()
        elif isinstance(value, tuple) and len(value) > 1:
            ordinary = tuple(
                frontend.emitter.classical_value(frame, item) for item in value
            )
        else:
            ordinary = (frontend.emitter.classical_value(frame, value),)
        outputs = (
            *ordinary,
            *(frontend.emitter.acquire(frame, value) for value in frontend.parameters),
        )
        frame.free_local_allocations()
        emit_return(frame, outputs)
        frontend.done.update(frame.output.stmts)
        frontend.ordinary_count = len(ordinary)
        frontend.output_count = len(outputs)

    def lower_Lambda(
        self, state: lowering.State[ast.AST], node: ast.Lambda
    ) -> lowering.Result:
        """Report closures that need a separate ownership calling convention."""
        raise lowering.BuildError("Wire lowering requires static helper calls.")
