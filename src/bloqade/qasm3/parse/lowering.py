from typing import Any
from dataclasses import field, dataclass

import openqasm3.ast as oq3_ast
from kirin import ir, types, lowering
from kirin.dialects import func

from bloqade.qasm3.types import QRegType, QubitType, BitRegType
from bloqade.qasm3.dialects import uop, core, expr

# Gate dispatch tables mapping QASM3 gate names to IR statement constructors
SINGLE_QUBIT_GATES: dict[str, type] = {
    "h": uop.H,
    "x": uop.X,
    "y": uop.Y,
    "z": uop.Z,
    "s": uop.S,
    "t": uop.T,
}

ROTATION_GATES: dict[str, type] = {
    "rx": uop.RX,
    "ry": uop.RY,
    "rz": uop.RZ,
}

TWO_QUBIT_GATES: dict[str, type] = {
    "cx": uop.CX,
    "cy": uop.CY,
    "cz": uop.CZ,
}

GENERAL_UNITARY: dict[str, type] = {
    "U": uop.UGate,
    "u3": uop.UGate,
}

# Unsupported constructs that raise BuildError
UNSUPPORTED_CONSTRUCTS = {
    "ForInLoop",
    "WhileLoop",
    "BranchingStatement",
    "SubroutineDefinition",
    "SwitchStatement",
}


@dataclass
class QASM3Lowering(lowering.LoweringABC[oq3_ast.QASMNode]):
    """Lowers openqasm3 AST nodes into QASM3 dialect IR."""

    max_lines: int = field(default=3, kw_only=True)
    hint_indent: int = field(default=2, kw_only=True)
    hint_show_lineno: bool = field(default=True, kw_only=True)
    stacktrace: bool = field(default=True, kw_only=True)

    def run(
        self,
        stmt: oq3_ast.QASMNode,
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
        stmt: oq3_ast.QASMNode,
        source: str | None = None,
        globals: dict[str, Any] | None = None,
        file: str | None = None,
        lineno_offset: int = 0,
        col_offset: int = 0,
        compactify: bool = True,
    ) -> lowering.Frame:
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

    def visit(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.QASMNode
    ) -> lowering.LoweringABC.Result:
        name = node.__class__.__name__

        if name in UNSUPPORTED_CONSTRUCTS:
            raise lowering.BuildError(f"Unsupported QASM3 construct: {name}")

        visitor = getattr(self, f"visit_{name}", None)
        if visitor is None:
            raise lowering.BuildError(f"Unsupported QASM3 construct: {name}")
        return visitor(state, node)

    def lower_global(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.QASMNode
    ) -> lowering.LoweringABC.Result:
        if isinstance(node, oq3_ast.Identifier):
            try:
                return lowering.LoweringABC.Result(
                    state.current_frame.globals[node.name]
                )
            except KeyError:
                pass
        raise lowering.BuildError("Global variables are not supported in QASM 3.0")

    def lower_literal(
        self, state: lowering.State[oq3_ast.QASMNode], value
    ) -> ir.SSAValue:
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

    # ---- Program ----

    def visit_Program(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.Program
    ):
        for stmt in node.statements:
            self.visit(state, stmt)

    # ---- Declarations ----

    def visit_QubitDeclaration(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.QubitDeclaration
    ):
        if node.size is None:
            # Single qubit: qubit q;
            size_val = self.lower_literal(state, 1)
        else:
            size_val = self._lower_expression(state, node.size)

        reg = core.QRegNew(n_qubits=size_val)
        state.current_frame.push(reg)
        reg.result.name = node.qubit.name
        state.current_frame.defs[node.qubit.name] = reg.result

    def visit_ClassicalDeclaration(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        node: oq3_ast.ClassicalDeclaration,
    ):
        if not isinstance(node.type, oq3_ast.BitType):
            raise lowering.BuildError(
                f"Unsupported classical type: {type(node.type).__name__}. "
                "Only bit registers are supported."
            )

        if node.type.size is None:
            # Single bit: bit c;
            size_val = self.lower_literal(state, 1)
        else:
            size_val = self._lower_expression(state, node.type.size)

        reg = core.BitRegNew(n_bits=size_val)
        state.current_frame.push(reg)
        reg.result.name = node.identifier.name
        state.current_frame.defs[node.identifier.name] = reg.result

    # ---- Gates ----

    def visit_QuantumGate(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.QuantumGate
    ):
        gate_name = node.name.name

        # Resolve qubit arguments
        qubits = [self._lower_qubit_ref(state, q) for q in node.qubits]

        # Resolve expression arguments (angles, etc.)
        params = [self._lower_expression(state, arg) for arg in node.arguments]

        if gate_name in SINGLE_QUBIT_GATES:
            if len(qubits) != 1:
                raise lowering.BuildError(
                    f"Gate '{gate_name}' expects 1 qubit, got {len(qubits)}"
                )
            stmt = SINGLE_QUBIT_GATES[gate_name](qarg=qubits[0])

        elif gate_name in ROTATION_GATES:
            if len(qubits) != 1 or len(params) != 1:
                raise lowering.BuildError(
                    f"Gate '{gate_name}' expects 1 qubit and 1 parameter"
                )
            stmt = ROTATION_GATES[gate_name](theta=params[0], qarg=qubits[0])

        elif gate_name in TWO_QUBIT_GATES:
            if len(qubits) != 2:
                raise lowering.BuildError(
                    f"Gate '{gate_name}' expects 2 qubits, got {len(qubits)}"
                )
            stmt = TWO_QUBIT_GATES[gate_name](ctrl=qubits[0], qarg=qubits[1])

        elif gate_name in GENERAL_UNITARY:
            if len(qubits) != 1 or len(params) != 3:
                raise lowering.BuildError(
                    f"Gate '{gate_name}' expects 1 qubit and 3 parameters"
                )
            stmt = GENERAL_UNITARY[gate_name](
                theta=params[0], phi=params[1], lam=params[2], qarg=qubits[0]
            )

        else:
            # Fallback: look up user-defined gate in globals and emit func.Invoke
            value = state.get_global(node.name).expect(ir.Method)
            if value.return_type is None:
                raise lowering.BuildError(f"Unknown return type for gate '{gate_name}'")
            stmt = func.Invoke(
                callee=value,
                inputs=tuple(params + qubits),
            )

        state.current_frame.push(stmt)

    # ---- Gate definitions ----

    def visit_QuantumGateDefinition(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        node: oq3_ast.QuantumGateDefinition,
    ):
        gate_name = node.name.name
        self_name = gate_name + "_self"

        # Classical angle params come first, then qubit params
        cparam_names = [arg.name for arg in node.arguments]
        qparam_names = [q.name for q in node.qubits]
        arg_names = cparam_names + qparam_names
        arg_types = [types.Float for _ in cparam_names] + [
            QubitType for _ in qparam_names
        ]

        with state.frame(
            stmts=node.body,
            finalize_next=False,
        ) as body_frame:
            # Insert _self as first block arg (method self-reference)
            body_frame.curr_block.args.append_from(
                types.Generic(
                    ir.Method, types.Tuple.where(tuple(arg_types)), types.NoneType
                ),
                name=self_name,
            )

            for arg_type, arg_name in zip(arg_types, arg_names):
                block_arg = body_frame.curr_block.args.append_from(
                    arg_type, name=arg_name
                )
                body_frame.defs[arg_name] = block_arg

            body_frame.exhaust()

            return_val = func.ConstantNone()
            body_frame.push(return_val)
            body_frame.push(func.Return(return_val))

            body = body_frame.curr_region

        gate_func = expr.GateFunction(
            sym_name=gate_name,
            signature=func.Signature(inputs=tuple(arg_types), output=types.NoneType),
            body=body,
        )

        mt = ir.Method(
            mod=None,
            py_func=None,
            sym_name=gate_name,
            dialects=self.dialects,
            arg_names=[self_name, *cparam_names, *qparam_names],
            code=gate_func,
        )
        state.current_frame.globals[gate_name] = mt

    # ---- Measurement ----

    def visit_QuantumMeasurementStatement(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        node: oq3_ast.QuantumMeasurementStatement,
    ):
        qarg = self._lower_qubit_ref(state, node.measure.qubit)
        carg = self._lower_bit_ref(state, node.target)
        state.current_frame.push(core.Measure(qarg=qarg, carg=carg))

    # ---- Reset ----

    def visit_QuantumReset(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.QuantumReset
    ):
        qarg = self._lower_qubit_ref(state, node.qubits)
        state.current_frame.push(core.Reset(qarg=qarg))

    # ---- Barrier ----

    def visit_QuantumBarrier(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.QuantumBarrier
    ):
        qargs = tuple(self._lower_qubit_ref(state, q) for q in node.qubits)
        state.current_frame.push(core.Barrier(qargs=qargs))

    # ---- Include (ignored for stdgates.inc) ----

    def visit_Include(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.Include
    ):
        if node.filename not in ("stdgates.inc",):
            raise lowering.BuildError(f"Unsupported include: {node.filename}")

    # ---- Expression lowering helpers ----

    def _lower_expression(
        self, state: lowering.State[oq3_ast.QASMNode], node: oq3_ast.Expression
    ) -> ir.SSAValue:
        """Lower an openqasm3 expression AST node to an IR SSAValue."""
        if isinstance(node, oq3_ast.IntegerLiteral):
            return self.lower_literal(state, node.value)

        elif isinstance(node, oq3_ast.FloatLiteral):
            return self.lower_literal(state, node.value)

        elif isinstance(node, oq3_ast.Identifier):
            if node.name == "pi":
                stmt = expr.ConstPI()
                state.current_frame.push(stmt)
                return stmt.result
            # Look up in defs
            val = state.current_frame.get_local(node.name)
            if val is not None:
                return val
            raise lowering.BuildError(f"Unknown identifier: '{node.name}'")

        elif isinstance(node, oq3_ast.BinaryExpression):
            return self._lower_binary_expression(state, node)

        elif isinstance(node, oq3_ast.UnaryExpression):
            return self._lower_unary_expression(state, node)

        else:
            raise lowering.BuildError(
                f"Unsupported expression type: {type(node).__name__}"
            )

    def _lower_binary_expression(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        node: oq3_ast.BinaryExpression,
    ) -> ir.SSAValue:
        lhs = self._lower_expression(state, node.lhs)
        rhs = self._lower_expression(state, node.rhs)

        op = node.op
        if op == oq3_ast.BinaryOperator["+"]:
            stmt = expr.Add(lhs=lhs, rhs=rhs)
        elif op == oq3_ast.BinaryOperator["-"]:
            stmt = expr.Sub(lhs=lhs, rhs=rhs)
        elif op == oq3_ast.BinaryOperator["*"]:
            stmt = expr.Mul(lhs=lhs, rhs=rhs)
        elif op == oq3_ast.BinaryOperator["/"]:
            stmt = expr.Div(lhs=lhs, rhs=rhs)
        else:
            raise lowering.BuildError(f"Unsupported binary operator: {op}")

        state.current_frame.push(stmt)
        return stmt.result

    def _lower_unary_expression(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        node: oq3_ast.UnaryExpression,
    ) -> ir.SSAValue:
        operand = self._lower_expression(state, node.expression)

        if node.op == oq3_ast.UnaryOperator["-"]:
            stmt = expr.Neg(value=operand)
            state.current_frame.push(stmt)
            return stmt.result
        else:
            raise lowering.BuildError(f"Unsupported unary operator: {node.op}")

    # ---- Qubit/Bit reference helpers ----

    def _lower_qubit_ref(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        ref: oq3_ast.Identifier | oq3_ast.IndexedIdentifier,
    ) -> ir.SSAValue:
        """Lower a qubit reference (e.g. q[0]) to an SSAValue."""
        if isinstance(ref, oq3_ast.IndexedIdentifier):
            reg_name = ref.name.name
            reg = state.current_frame.get_local(reg_name)
            if reg is None:
                raise lowering.BuildError(f"Undefined register: '{reg_name}'")

            # indices is List[IndexElement] where IndexElement = List[Expression | Range]
            # For simple indexing like q[0], indices = [[IntegerLiteral(0)]]
            if len(ref.indices) != 1 or len(ref.indices[0]) != 1:
                raise lowering.BuildError(
                    f"Only simple integer indexing is supported, got: {ref.indices}"
                )
            idx = self._lower_expression(state, ref.indices[0][0])

            if reg.type.is_subseteq(QRegType):
                stmt = core.QRegGet(reg=reg, idx=idx)
            else:
                raise lowering.BuildError(
                    f"Expected quantum register for qubit reference, got {reg.type}"
                )
            state.current_frame.push(stmt)
            return stmt.result

        elif isinstance(ref, oq3_ast.Identifier):
            val = state.current_frame.get_local(ref.name)
            if val is None:
                raise lowering.BuildError(f"Undefined qubit: '{ref.name}'")
            return val

        else:
            raise lowering.BuildError(
                f"Unsupported qubit reference type: {type(ref).__name__}"
            )

    def _lower_bit_ref(
        self,
        state: lowering.State[oq3_ast.QASMNode],
        ref: oq3_ast.Identifier | oq3_ast.IndexedIdentifier,
    ) -> ir.SSAValue:
        """Lower a bit reference (e.g. c[0]) to an SSAValue."""
        if isinstance(ref, oq3_ast.IndexedIdentifier):
            reg_name = ref.name.name
            reg = state.current_frame.get_local(reg_name)
            if reg is None:
                raise lowering.BuildError(f"Undefined register: '{reg_name}'")

            if len(ref.indices) != 1 or len(ref.indices[0]) != 1:
                raise lowering.BuildError(
                    f"Only simple integer indexing is supported, got: {ref.indices}"
                )
            idx = self._lower_expression(state, ref.indices[0][0])

            if reg.type.is_subseteq(BitRegType):
                stmt = core.BitRegGet(reg=reg, idx=idx)
            else:
                raise lowering.BuildError(
                    f"Expected bit register for bit reference, got {reg.type}"
                )
            state.current_frame.push(stmt)
            return stmt.result

        elif isinstance(ref, oq3_ast.Identifier):
            val = state.current_frame.get_local(ref.name)
            if val is None:
                raise lowering.BuildError(f"Undefined bit: '{ref.name}'")
            return val

        else:
            raise lowering.BuildError(
                f"Unsupported bit reference type: {type(ref).__name__}"
            )
