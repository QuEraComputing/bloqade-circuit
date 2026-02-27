"""Main QASM3 emitter using EmitABC with method-table dispatch."""

from dataclasses import dataclass

from kirin import ir, interp
from kirin.dialects import func
from kirin.ir.dialect import Dialect as Dialect
from typing_extensions import Self

from bloqade.qasm3.types import QubitType
from bloqade.qasm3.dialects.expr.stmts import GateFunction

from .base import EmitQASM3Base, EmitQASM3Frame


@dataclass
class EmitQASM3Main(EmitQASM3Base):
    keys = ("emit.qasm3.main", "emit.qasm3.gate")
    dialects: ir.DialectGroup

    def initialize(self) -> Self:
        super().initialize()
        return self

    def eval_fallback(self, frame: EmitQASM3Frame, node: ir.Statement):
        return tuple(None for _ in range(len(node.results)))


@func.dialect.register(key="emit.qasm3.main")
class Func(interp.MethodTable):

    @interp.impl(func.Invoke)
    def invoke(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: func.Invoke
    ):
        callee = stmt.callee
        gate_name = callee.sym_name

        # After QASM3ToSquin, QRegNew may be rewritten to func.invoke qalloc.
        if gate_name == "qalloc":
            size_str = frame.get(stmt.args[0])
            name = emit.ssa_id[stmt.result]
            frame.body.append(f"qubit[{size_str}] {name};")
            return (name,)

        # Register the callee for gate definition emission
        callee_name = emit.callables.get(callee.code)
        if callee_name is None:
            callee_name = emit.callables.add(callee.code)
            emit.callable_to_emit.append(callee.code)

        # Separate classical params from qubit args using callee signature
        callee_params = list(callee.code.body.blocks[0].args)[1:]  # skip self
        qargs: list[str] = []
        cparams: list[str] = []
        for arg, param in zip(stmt.args, callee_params):
            resolved = frame.get(arg)
            if resolved is None:
                continue
            if param.type.is_subseteq(QubitType):
                qargs.append(str(resolved))
            else:
                cparams.append(str(resolved))

        if cparams:
            line = f"{gate_name}({', '.join(cparams)}) {', '.join(qargs)};"
        else:
            line = f"{gate_name} {', '.join(qargs)};"
        frame.body.append(line)
        return ()

    @interp.impl(func.Function)
    def emit_func(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: func.Function
    ):
        if isinstance(stmt, GateFunction):
            return ()

        func_name = emit.callables.get(stmt)
        if func_name is None:
            func_name = emit.callables.add(stmt)

        for block in stmt.body.blocks:
            frame.current_block = block
            for s in block.stmts:
                frame.current_stmt = s
                stmt_results = emit.frame_eval(frame, s)
                if isinstance(stmt_results, tuple):
                    if len(stmt_results) != 0:
                        frame.set_values(s._results, stmt_results)
                    continue

        # Emit gate definitions
        gate_defs: list[str] = []
        from bloqade.qasm3.emit.gate import EmitQASM3Gate

        gate_emitter = EmitQASM3Gate(dialects=emit.dialects).initialize()
        gate_emitter.callables = emit.callables

        while emit.callable_to_emit:
            callable_node = emit.callable_to_emit.pop()
            if callable_node is None:
                break

            if isinstance(callable_node, GateFunction):
                with gate_emitter.eval_context():
                    with gate_emitter.new_frame(
                        callable_node, has_parent_access=False
                    ) as gate_frame:
                        gate_emitter.frame_eval(gate_frame, callable_node)
                        if gate_emitter.output is not None:
                            gate_defs.append(gate_emitter.output)
                            gate_emitter.output = None

        emit.output = "\n".join(gate_defs + frame.body)
        return ()

    @interp.impl(func.Return)
    def emit_return(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: func.Return
    ):
        return ()

    @interp.impl(func.ConstantNone)
    def emit_constant_none(
        self, emit: EmitQASM3Main, frame: EmitQASM3Frame, stmt: func.ConstantNone
    ):
        return (None,)
