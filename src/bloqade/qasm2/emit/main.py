from dataclasses import dataclass, field
from typing_extensions import Self
from typing import cast, List

from kirin import ir, interp
from kirin.dialects import cf, scf, func
from kirin.ir.dialect import Dialect as Dialect
from kirin.worklist import WorkList
from .base import EmitQASM2Base, EmitQASM2Frame, SymbolTable

from bloqade.qasm2.parse import ast
from bloqade.qasm2.dialects.uop import SingleQubitGate, TwoQubitCtrlGate
from bloqade.qasm2.dialects.expr import GateFunction

from ..dialects.core.stmts import Reset, Measure

@dataclass
class EmitQASM2Main(EmitQASM2Base[ast.Statement, ast.MainProgram]):
    keys = ("emit.qasm2.main", "emit.qasm2.gate")
    dialects: ir.DialectGroup
    callable_to_emit: WorkList[ir.Statement] = field(init=False)

    def initialize(self) -> Self:
        super().initialize()
        self.callables: SymbolTable = SymbolTable(prefix="")
        self.callable_to_emit = WorkList()
        return self

    def run(self, node: ir.Method | ir.Statement):
        if isinstance(node, ir.Method):
            node = node.code
        with self.eval_context():
            self.callable_to_emit.append(node)
            while self.callable_to_emit:
                callable = self.callable_to_emit.pop()
                if callable is None:
                    break
                self.eval(callable)
        return


@func.dialect.register(key="emit.qasm2.main")
class Func(interp.MethodTable):
    @interp.impl(func.Return)
    @interp.impl(func.ConstantNone)
    def ignore(self, emit: EmitQASM2Main, frame: EmitQASM2Frame, stmt):
        return ()
    
    @interp.impl(func.Invoke)
    def invoke(
        self, emit: EmitQASM2Main, frame: EmitQASM2Frame, node: func.Invoke
    ):
        name = emit.callables.get(node.callee.code)
        if name is None:
            name = emit.callables.add(node.callee.code)
            emit.callable_to_emit.append(node.callee.code)

        if isinstance(node.callee.code, GateFunction):
            c_params: list[ast.Expr] = []
            q_args: list[ast.Bit | ast.Name] = []

            for arg in node.args:
                val = frame.get(arg)
                if val is None:
                    raise interp.InterpreterError(f"missing mapping for arg {arg}")
                if isinstance(val, (ast.Bit, ast.Name)):
                    q_args.append(val)
                elif isinstance(val, ast.Expr):
                    c_params.append(val)

            instr = ast.Instruction(
                name=ast.Name(name) if isinstance(name, str) else name,
                params=c_params,
                qargs=q_args
            )
            frame.body.append(instr)
            return ()

        callee_name_node = ast.Name(name) if isinstance(name, str) else name
        args = tuple(frame.get_values(node.args))
        _, call_expr = emit.call(node.callee.code, callee_name_node, *args)
        if call_expr is not None:
            frame.body.append(call_expr)
        return ()

    @interp.impl(func.Function)
    def emit_func(
        self, emit: EmitQASM2Main, frame: EmitQASM2Frame, stmt: func.Function
    ):
        from bloqade.qasm2.dialects import glob, parallel
        from bloqade.qasm2.emit.gate import EmitQASM2Gate

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

        gate_defs: list[ast.Gate] = []
        
        gate_emitter = EmitQASM2Gate(dialects=emit.dialects).initialize()
        gate_emitter.callables = emit.callables
         
        while emit.callable_to_emit:
            callable_node = emit.callable_to_emit.pop()
            if callable_node is None:
                break
            
            if isinstance(callable_node, GateFunction):
                with gate_emitter.eval_context():
                    with gate_emitter.new_frame(callable_node, has_parent_access=False) as gate_frame:
                        gate_result = gate_emitter.frame_eval(gate_frame, callable_node)
                        gate_obj = None
                        if isinstance(gate_result, tuple) and len(gate_result) > 0:
                            maybe = gate_result[0]
                            if isinstance(maybe, ast.Gate):
                                gate_obj = maybe

                        if gate_obj is None:
                            name = emit.callables.get(callable_node) or emit.callables.add(callable_node)
                            prefix = getattr(emit.callables, "prefix", "") or ""
                            emit_name = name[len(prefix) :] if prefix and name.startswith(prefix) else name
                            gate_obj = ast.Gate(name=emit_name, cparams=[], qparams=[], body=[])

                        gate_defs.append(gate_obj)
                
        if emit.dialects.data.intersection((parallel.dialect, glob.dialect)):
            header = ast.Kirin([dialect.name for dialect in emit.dialects])
        else:
            header = ast.OPENQASM(ast.Version(2, 0))

        full_body = gate_defs + frame.body
        stmt_list = cast(List[ast.Statement], full_body)
        emit.output = ast.MainProgram(header=header, statements=stmt_list)
        return ()


@cf.dialect.register(key="emit.qasm2.main")
class Cf(interp.MethodTable):

    @interp.impl(cf.Branch)
    def emit_branch(self, emit: EmitQASM2Main, frame: EmitQASM2Frame, stmt: cf.Branch):
        frame.worklist.append(
            interp.Successor(stmt.successor, frame.get_values(stmt.arguments))
        )
        return ()

    @interp.impl(cf.ConditionalBranch)
    def emit_conditional_branch(
        self, emit: EmitQASM2Main, frame: EmitQASM2Frame, stmt: cf.ConditionalBranch
    ):
        cond = emit.assert_node(ast.Cmp, frame.get(stmt.cond))

        with emit.new_frame(stmt) as body_frame:
            body_frame.entries.update(frame.entries)
            body_frame.set_values(
                stmt.then_successor.args, frame.get_values(stmt.then_arguments)
            )
            emit.emit_block(body_frame, stmt.then_successor)

        frame.body.append(
            ast.IfStmt(
                cond,
                body=body_frame.body,  # type: ignore
            )
        )
        frame.worklist.append(
            interp.Successor(stmt.else_successor, frame.get_values(stmt.else_arguments))
        )
        return ()


@scf.dialect.register(key="emit.qasm2.main")
class Scf(interp.MethodTable):

    @interp.impl(scf.Yield)
    def emit_yield(self, emit: EmitQASM2Main, frame: EmitQASM2Frame, stmt: scf.Yield):
        return frame.get_values(stmt.values)

    @interp.impl(scf.IfElse)
    def emit_if_else(
        self, emit: EmitQASM2Main, frame: EmitQASM2Frame, stmt: scf.IfElse
    ):
        else_stmts = stmt.else_body.blocks[0].stmts
        if not (
            len(else_stmts) == 0
            or len(else_stmts) == 1
            and isinstance(else_stmts.at(0), scf.Yield)
        ):
            raise interp.InterpreterError(
                "cannot lower if-else with non-empty else block"
            )

        cond = emit.assert_node(ast.Cmp, frame.get(stmt.cond))

        # NOTE: we need exactly one of those in the then body in order to emit valid QASM2
        AllowedThenType = SingleQubitGate | TwoQubitCtrlGate | Measure | Reset

        then_stmts = stmt.then_body.blocks[0].stmts
        uop_stmts = 0
        for s in then_stmts:
            if isinstance(s, AllowedThenType):
                uop_stmts += 1
                continue

            if isinstance(s, func.Invoke):
                uop_stmts += isinstance(s.callee.code, GateFunction)

        if uop_stmts != 1:
            raise interp.InterpreterError(
                "Cannot lower if-statement: QASM2 only allows exactly one quantum operation in the body."
            )

        with emit.new_frame(stmt) as then_frame:
            then_frame.entries.update(frame.entries)
            emit.emit_block(then_frame, stmt.then_body.blocks[0])
            frame.body.append(
                ast.IfStmt(
                    cond,
                    body=then_frame.body,  # type: ignore
                )
            )

        term = stmt.then_body.blocks[0].last_stmt
        if isinstance(term, scf.Yield):
            return then_frame.get_values(term.values)
        return ()
