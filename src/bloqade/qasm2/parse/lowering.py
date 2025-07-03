from typing import Any
from dataclasses import field, dataclass

from kirin import ir, types, lowering
from kirin.dialects import cf, scf, func, ilist

from bloqade.qasm2.types import CRegType, QRegType, QubitType
from bloqade.qasm2.dialects import uop, core, expr, glob, noise, parallel

from . import ast


@dataclass
class QASM2(lowering.LoweringABC[ast.Node]):
    max_lines: int = field(default=3, kw_only=True)
    hint_indent: int = field(default=2, kw_only=True)
    hint_show_lineno: bool = field(default=True, kw_only=True)
    stacktrace: bool = field(default=True, kw_only=True)

    def run(
        self,
        stmt: ast.Node,
        *,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> ir.Region:

        frame = self.get_frame(
            stmt,
            source=source,
            globals=globals,
            file=file,
            lineno_offset=lineno_offset,
            col_offset=col_offset,
            compactify=compactify,
        )

        return frame.curr_region

    def get_frame(
        self,
        stmt: ast.Node,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> lowering.Frame:
        # TODO: add source info
        state = lowering.State(
            self,
            file=file,
            lineno_offset=lineno_offset,
            col_offset=col_offset,
        )
        with state.frame(
            [stmt],
            globals=globals,
            finalize_next=False,
        ) as frame:
            self.visit(state, stmt)

            if compactify:
                from kirin.rewrite import Walk, CFGCompactify

                Walk(CFGCompactify()).rewrite(frame.curr_region)

            return frame

    def visit(self, state: lowering.State[ast.Node], node: ast.Node) -> lowering.Result:
        name = node.__class__.__name__
        return getattr(self, f"visit_{name}", self.generic_visit)(state, node)

    def generic_visit(
        self, state: lowering.State[ast.Node], node: ast.Node
    ) -> lowering.Result:
        if isinstance(node, ast.Node):
            raise lowering.BuildError(
                f"Cannot lower {node.__class__.__name__} node: {node}"
            )
        raise lowering.BuildError(
            f"Unexpected `{node.__class__.__name__}` node: {repr(node)} is not an AST node"
        )

    def lower_literal(self, state: lowering.State[ast.Node], value) -> ir.SSAValue:
        if isinstance(value, int):
            stmt = expr.ConstInt(value=value)
        elif isinstance(value, float):
            stmt = expr.ConstFloat(value=value)
        else:
            raise lowering.BuildError(
                f"Expected value of type float or int, got {type(value)}."
            )
        state.current_frame.push(stmt)
        return stmt.result

    def lower_global(
        self, state: lowering.State[ast.Node], node: ast.Node
    ) -> lowering.LoweringABC.Result:
        if isinstance(node, ast.Name):
            # NOTE: might be a lookup for a gate function invoke
            try:
                return lowering.LoweringABC.Result(state.current_frame.globals[node.id])
            except KeyError:
                pass

        raise lowering.BuildError("Global variables are not supported in QASM 2.0")

    def visit_MainProgram(self, state: lowering.State[ast.Node], node: ast.MainProgram):
        allowed = {dialect.name for dialect in self.dialects}
        if isinstance(node.header, ast.OPENQASM) and node.header.version.major == 2:
            dialects = ["qasm2.core", "qasm2.uop", "qasm2.expr"]
        elif isinstance(node.header, ast.Kirin):
            dialects = node.header.dialects
        else:
            raise lowering.BuildError(f"Unexpected node header {node.header}")

        for dialect in dialects:
            if dialect not in allowed:
                raise lowering.BuildError(
                    f"Dialect {dialect} not found, allowed: {', '.join(allowed)}"
                )

        for stmt in node.statements:
            state.lower(stmt)

    def visit_QReg(self, state: lowering.State[ast.Node], node: ast.QReg):
        reg = core.QRegNew(
            state.current_frame.push(expr.ConstInt(value=node.size)).result
        )
        state.current_frame.push(reg)
        state.current_frame.defs[node.name] = reg.result

    def visit_CReg(self, state: lowering.State[ast.Node], node: ast.CReg):
        reg = core.CRegNew(
            state.current_frame.push(expr.ConstInt(value=node.size)).result
        )
        state.current_frame.push(reg)
        state.current_frame.defs[node.name] = reg.result

    def visit_Barrier(self, state: lowering.State[ast.Node], node: ast.Barrier):
        state.current_frame.push(
            uop.Barrier(
                qargs=tuple(state.lower(qarg).expect_one() for qarg in node.qargs)
            )
        )

    def visit_CXGate(self, state: lowering.State[ast.Node], node: ast.CXGate):
        state.current_frame.push(
            uop.CX(
                ctrl=state.lower(node.ctrl).expect_one(),
                qarg=state.lower(node.qarg).expect_one(),
            )
        )

    def visit_Measure(self, state: lowering.State[ast.Node], node: ast.Measure):
        state.current_frame.push(
            core.Measure(
                qarg=state.lower(node.qarg).expect_one(),
                carg=state.lower(node.carg).expect_one(),
            )
        )

    def visit_UGate(self, state: lowering.State[ast.Node], node: ast.UGate):
        state.current_frame.push(
            uop.UGate(
                theta=state.lower(node.theta).expect_one(),
                phi=state.lower(node.phi).expect_one(),
                lam=state.lower(node.lam).expect_one(),
                qarg=state.lower(node.qarg).expect_one(),
            )
        )

    def visit_Reset(self, state: lowering.State[ast.Node], node: ast.Reset):
        state.current_frame.push(core.Reset(qarg=state.lower(node.qarg).expect_one()))

    def visit_IfStmt(self, state: lowering.State[ast.Node], node: ast.IfStmt):
        cond_stmt = core.CRegEq(
            lhs=state.lower(node.cond.lhs).expect_one(),
            rhs=state.lower(node.cond.rhs).expect_one(),
        )
        cond = state.current_frame.push(cond_stmt).result
        frame = state.current_frame

        with state.frame(node.body) as if_frame:
            true_cond = if_frame.entr_block.args.append_from(types.Bool, cond.name)
            if cond.name:
                if_frame.defs[cond.name] = true_cond

            # NOTE: pass in definitions from outer scope (usually just for the qreg)
            if_frame.defs.update(frame.defs)

            if_frame.exhaust()

            # NOTE: qasm2 can never yield anything from if
            if_frame.push(scf.Yield())

            then_body = if_frame.curr_region

        state.current_frame.push(scf.IfElse(cond, then_body=then_body))

    def branch_next_if_not_terminated(self, frame: lowering.Frame):
        """Branch to the next block if the current block is not terminated.

        This must be used after exhausting the current frame and before popping the frame.
        """
        if not frame.curr_block.last_stmt or not frame.curr_block.last_stmt.has_trait(
            ir.IsTerminator
        ):
            frame.curr_block.stmts.append(
                cf.Branch(arguments=(), successor=frame.next_block)
            )

    def visit_BinOp(self, state: lowering.State[ast.Node], node: ast.BinOp):
        if node.op == "+":
            stmt_type = expr.Add
        elif node.op == "-":
            stmt_type = expr.Sub
        elif node.op == "*":
            stmt_type = expr.Mul
        else:
            stmt_type = expr.Div

        return state.current_frame.push(
            stmt_type(
                lhs=state.lower(node.lhs).expect_one(),
                rhs=state.lower(node.rhs).expect_one(),
            )
        )

    def visit_UnaryOp(self, state: lowering.State[ast.Node], node: ast.UnaryOp):
        if node.op == "-":
            stmt = expr.Neg(value=state.lower(node.operand).expect_one())
            return state.current_frame.push(stmt).result
        else:
            return state.lower(node.operand).expect_one()

    def visit_Bit(self, state: lowering.State[ast.Node], node: ast.Bit):
        if node.name.id not in state.current_frame.defs:
            raise ValueError(f"Bit {node.name} not found")

        addr = state.current_frame.push(expr.ConstInt(value=node.addr))
        reg = state.current_frame.get_local(node.name.id)
        if reg is None:
            raise lowering.BuildError(f"{node.name.id} is not defined")

        if reg.type.is_subseteq(QRegType):
            stmt = core.QRegGet(reg, addr.result)
        elif reg.type.is_subseteq(CRegType):
            stmt = core.CRegGet(reg, addr.result)
        else:
            raise lowering.BuildError(f"Unexpected register type {reg.type}")
        return state.current_frame.push(stmt).result

    def visit_Call(self, state: lowering.State[ast.Node], node: ast.Call):
        if node.name == "cos":
            stmt = expr.Cos(state.lower(node.args[0]).expect_one())
        elif node.name == "sin":
            stmt = expr.Sin(state.lower(node.args[0]).expect_one())
        elif node.name == "tan":
            stmt = expr.Tan(state.lower(node.args[0]).expect_one())
        elif node.name == "exp":
            stmt = expr.Exp(state.lower(node.args[0]).expect_one())
        elif node.name == "log":
            stmt = expr.Log(state.lower(node.args[0]).expect_one())
        elif node.name == "sqrt":
            stmt = expr.Sqrt(state.lower(node.args[0]).expect_one())
        else:
            raise ValueError(f"Unknown function {node.name}")
        state.current_frame.push(stmt)
        return stmt.result

    def visit_Name(self, state: lowering.State[ast.Node], node: ast.Name):
        if (value := state.current_frame.get_local(node.id)) is not None:
            return value
        raise ValueError(f"name {node.id} not found")

    def visit_ParaCZGate(self, state: lowering.State[ast.Node], node: ast.ParaCZGate):
        ctrls: list[ir.SSAValue] = []
        qargs: list[ir.SSAValue] = []
        for pair in node.qargs:
            if len(pair) != 2:
                raise ValueError("CZ gate requires exactly two qargs")
            ctrl, qarg = pair
            ctrls.append(state.lower(ctrl).expect_one())
            qargs.append(state.lower(qarg).expect_one())

        ctrls_stmt = ilist.New(values=ctrls)
        qargs_stmt = ilist.New(values=qargs)
        state.current_frame.push(ctrls_stmt)
        state.current_frame.push(qargs_stmt)
        state.current_frame.push(
            parallel.CZ(ctrls=ctrls_stmt.result, qargs=qargs_stmt.result)
        )

    def visit_ParaRZGate(self, state: lowering.State[ast.Node], node: ast.ParaRZGate):
        qargs: list[ir.SSAValue] = []
        for pair in node.qargs:
            if len(pair) != 1:
                raise ValueError("Rz gate requires exactly one qarg")
            qargs.append(state.lower(pair[0]).expect_one())

        qargs_stmt = ilist.New(values=qargs)
        state.current_frame.push(qargs_stmt)
        state.current_frame.push(
            parallel.RZ(
                theta=state.lower(node.theta).expect_one(),
                qargs=qargs_stmt.result,
            )
        )

    def visit_ParaU3Gate(self, state: lowering.State[ast.Node], node: ast.ParaU3Gate):
        qargs: list[ir.SSAValue] = []
        for pair in node.qargs:
            if len(pair) != 1:
                raise ValueError("U3 gate requires exactly one qarg")
            qargs.append(state.lower(pair[0]).expect_one())

        qargs_stmt = ilist.New(values=qargs)
        state.current_frame.push(qargs_stmt)
        state.current_frame.push(
            parallel.UGate(
                theta=state.lower(node.theta).expect_one(),
                phi=state.lower(node.phi).expect_one(),
                lam=state.lower(node.lam).expect_one(),
                qargs=qargs_stmt.result,
            )
        )

    def visit_GlobUGate(self, state: lowering.State[ast.Node], node: ast.GlobUGate):
        registers: list[ir.SSAValue] = []

        for register in node.registers:  # These will all be ast.Names
            registers.append(state.lower(register).expect_one())

        registers_stmt = ilist.New(values=registers)
        state.current_frame.push(registers_stmt)
        state.current_frame.push(
            # all the stuff going into the args should be SSA values
            glob.UGate(
                registers=registers_stmt.result,  # expect_one = a singular SSA value
                theta=state.lower(node.theta).expect_one(),
                phi=state.lower(node.phi).expect_one(),
                lam=state.lower(node.lam).expect_one(),
            )
        )

    def visit_NoisePAULI1(self, state: lowering.State[ast.Node], node: ast.NoisePAULI1):
        state.current_frame.push(
            noise.Pauli1(
                px=state.lower(node.px).expect_one(),
                py=state.lower(node.py).expect_one(),
                pz=state.lower(node.pz).expect_one(),
                qarg=state.lower(node.qarg).expect_one(),
            )
        )

    def visit_Number(self, state: lowering.State[ast.Node], node: ast.Number):
        if isinstance(node.value, int):
            stmt = expr.ConstInt(value=node.value)
        else:
            stmt = expr.ConstFloat(value=node.value)
        state.current_frame.push(stmt)
        return stmt

    def visit_Pi(self, state: lowering.State[ast.Node], node: ast.Pi):
        return state.current_frame.push(expr.ConstPI()).result

    def visit_Include(self, state: lowering.State[ast.Node], node: ast.Include):
        if node.filename not in ["qelib1.inc"]:
            raise lowering.BuildError(f"Include {node.filename} not found")

    def visit_Gate(self, state: lowering.State[ast.Node], node: ast.Gate):
        arg_names = node.cparams + node.qparams
        arg_types = [types.Float for _ in node.cparams] + [
            QubitType for _ in node.qparams
        ]

        with state.frame(
            stmts=node.body,
            finalize_next=False,
        ) as body_frame:
            # NOTE: insert _self as arg
            body_frame.curr_block.args.append_from(
                types.Generic(
                    ir.Method, types.Tuple.where(tuple(arg_types)), types.NoneType
                ),
                name=node.name + "_self",
            )

            for arg_type, arg_name in zip(arg_types, arg_names):
                # NOTE: append args as block arguments
                block_arg = body_frame.curr_block.args.append_from(
                    arg_type, name=arg_name
                )

                # NOTE: add arguments as definitions to frame
                body_frame.defs[arg_name] = block_arg

            body_frame.exhaust()

            # NOTE: append none as return value
            return_val = func.ConstantNone()
            body_frame.push(return_val)
            body_frame.push(func.Return(return_val))

            body = body_frame.curr_region

        gate_func = expr.GateFunction(
            sym_name=node.name,
            signature=func.Signature(inputs=tuple(arg_types), output=types.NoneType),
            body=body,
        )

        mt = ir.Method(
            mod=None,
            py_func=None,
            sym_name=node.name,
            dialects=self.dialects,
            arg_names=[*node.cparams, *node.qparams],
            code=gate_func,
        )
        state.current_frame.globals[node.name] = mt

    def visit_Instruction(self, state: lowering.State[ast.Node], node: ast.Instruction):
        params = [state.lower(param).expect_one() for param in node.params]
        qargs = [state.lower(qarg).expect_one() for qarg in node.qargs]
        visit_inst = getattr(self, "visit_Instruction_" + node.name.id, None)
        if visit_inst is not None:
            state.current_frame.push(visit_inst(params, qargs))
        else:
            value = state.get_global(node.name).expect(ir.Method)
            # NOTE: QASM expects the return type to be known at call site
            if value.return_type is None:
                raise ValueError(f"Unknown return type for {node.name.id}")
            state.current_frame.push(
                func.Invoke(
                    callee=value,
                    inputs=tuple(params + qargs),
                    kwargs=tuple(),
                )
            )

    def visit_Instruction_id(self, params, qargs):
        return uop.Id(qarg=qargs[0])

    def visit_Instruction_x(self, params, qargs):
        return uop.X(qarg=qargs[0])

    def visit_Instruction_y(self, params, qargs):
        return uop.Y(qarg=qargs[0])

    def visit_Instruction_z(self, params, qargs):
        return uop.Z(qarg=qargs[0])

    def visit_Instruction_h(self, params, qargs):
        return uop.H(qarg=qargs[0])

    def visit_Instruction_s(self, params, qargs):
        return uop.S(qarg=qargs[0])

    def visit_Instruction_sdg(self, params, qargs):
        return uop.Sdag(qarg=qargs[0])

    def visit_Instruction_sx(self, params, qargs):
        return uop.SX(qarg=qargs[0])

    def visit_Instruction_sxdg(self, params, qargs):
        return uop.SXdag(qarg=qargs[0])

    def visit_Instruction_t(self, params, qargs):
        return uop.T(qarg=qargs[0])

    def visit_Instruction_tdg(self, params, qargs):
        return uop.Tdag(qarg=qargs[0])

    def visit_Instruction_rx(self, params, qargs):
        return uop.RX(theta=params[0], qarg=qargs[0])

    def visit_Instruction_ry(self, params, qargs):
        return uop.RY(theta=params[0], qarg=qargs[0])

    def visit_Instruction_rz(self, params, qargs):
        return uop.RZ(theta=params[0], qarg=qargs[0])

    def visit_Instruction_p(self, params, qargs):
        return uop.U1(lam=params[0], qarg=qargs[0])

    def visit_Instruction_u(self, params, qargs):
        return uop.UGate(theta=params[0], phi=params[1], lam=params[2], qarg=qargs[0])

    def visit_Instruction_u1(self, params, qargs):
        return uop.U1(lam=params[0], qarg=qargs[0])

    def visit_Instruction_u2(self, params, qargs):
        return uop.U2(phi=params[0], lam=params[1], qarg=qargs[0])

    def visit_Instruction_u3(self, params, qargs):
        return uop.UGate(theta=params[0], phi=params[1], lam=params[2], qarg=qargs[0])

    def visit_Instruction_CX(self, params, qargs):
        return uop.CX(ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cx(self, params, qargs):
        return uop.CX(ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cy(self, params, qargs):
        return uop.CY(ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cz(self, params, qargs):
        return uop.CZ(ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_ch(self, params, qargs):
        return uop.CH(ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_crx(self, params, qargs):
        return uop.CRX(lam=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cry(self, params, qargs):
        return uop.CRY(lam=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_crz(self, params, qargs):
        return uop.CRZ(lam=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_ccx(self, params, qargs):
        return uop.CCX(ctrl1=qargs[0], ctrl2=qargs[1], qarg=qargs[2])

    def visit_Instruction_csx(self, params, qargs):
        return uop.CSX(ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cswap(self, params, qargs):
        return uop.CSwap(ctrl=qargs[0], qarg1=qargs[1], qarg2=qargs[2])

    def visit_Instruction_cp(self, params, qargs):
        return uop.CU1(lam=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cu1(self, params, qargs):
        return uop.CU1(lam=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_cu3(self, params, qargs):
        return uop.CU3(
            theta=params[0], phi=params[1], lam=params[2], ctrl=qargs[0], qarg=qargs[1]
        )

    def visit_Instruction_cu(self, params, qargs):
        return uop.CU3(
            theta=params[0], phi=params[1], lam=params[2], ctrl=qargs[0], qarg=qargs[1]
        )

    def visit_Instruction_rxx(self, params, qargs):
        return uop.RXX(theta=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_rzz(self, params, qargs):
        return uop.RZZ(theta=params[0], ctrl=qargs[0], qarg=qargs[1])

    def visit_Instruction_swap(self, params, qargs):
        return uop.Swap(ctrl=qargs[0], qarg=qargs[1])
