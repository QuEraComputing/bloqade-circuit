from kirin import ir, types, interp, lowering
from kirin.decl import info, statement

from bloqade.qasm2.parse import ast
from bloqade.qasm2.types import QubitType
from bloqade.qasm2.emit.gate import EmitQASM2Gate, EmitQASM2Frame

dialect = ir.Dialect("qasm2.noise")


@statement(dialect=dialect)
class Pauli1(ir.Statement):
    name = "pauli_1"
    traits = frozenset({lowering.FromPythonCall()})
    px: ir.SSAValue = info.argument(types.Float)
    py: ir.SSAValue = info.argument(types.Float)
    pz: ir.SSAValue = info.argument(types.Float)
    qarg: ir.SSAValue = info.argument(QubitType)


@dialect.register(key="emit.qasm2.gate")
class NoiseEmit(interp.MethodTable):

    @interp.impl(Pauli1)
    def emit_pauli(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: Pauli1,
    ):

        px: ast.Number = frame.get(stmt.px)
        py: ast.Number = frame.get(stmt.py)
        pz: ast.Number = frame.get(stmt.pz)
        qarg: ast.Bit | ast.Name = frame.get(stmt.qarg)

        qarg_str = (
            f"{qarg.name.id}[{qarg.addr}]"
            if isinstance(qarg, ast.Bit)
            else f"{qarg.id}"
        )

        frame.body.append(
            ast.Comment(
                text=f"noise.Pauli1({px.value}, {py.value}, {pz.value}) {qarg_str}]"
            )
        )
        return ()
