from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.qasm2.parse import ast
from bloqade.qasm2.emit.gate import EmitQASM2Gate, EmitQASM2Frame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.qasm2.gate")
class NativeNoise(interp.MethodTable):

    @interp.impl(stmts.CZPauliChannel)
    def emit_czp(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: stmts.CZPauliChannel,
    ):
        paired: bool = stmt.paired
        px_ctrl: float = stmt.px_ctrl
        py_ctrl: float = stmt.py_ctrl
        pz_ctrl: float = stmt.pz_ctrl
        px_qarg: float = stmt.pz_qarg
        py_qarg: float = stmt.py_qarg
        pz_qarg: float = stmt.pz_qarg
        ctrls: ilist.IList[ast.Bit, Any] = frame.get(stmt.ctrls)
        qargs: ilist.IList[ast.Bit, Any] = frame.get(stmt.qargs)
        frame.body.append(
            ast.Comment(
                text=f"native.CZPauliChannel(paired={paired}, p_ctrl[{px_ctrl}, {py_ctrl}, {pz_ctrl}], p_qarg[{px_qarg}, {py_qarg}, {pz_qarg}])"
            )
        )
        frame.body.append(
            ast.Comment(
                text=f" -: ctrls: {', '.join([f'{q.name.id}[{q.addr}]' for q in ctrls])}"
            )
        )
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([f'{q.name.id}[{q.addr}]' for q in qargs])}"
            )
        )
        return ()

    @interp.impl(stmts.AtomLossChannel)
    def emit_loss(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: stmts.AtomLossChannel,
    ):
        prob: float = stmt.prob
        qargs: ilist.IList[ast.Bit, Any] = frame.get(stmt.qargs)
        frame.body.append(ast.Comment(text=f"native.Atomloss(p={prob})"))
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([f'{q.name.id}[{q.addr}]' for q in qargs])}"
            )
        )
        return ()

    @interp.impl(stmts.PauliChannel)
    def emit_loss(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: stmts.PauliChannel,
    ):
        px: float = stmt.px
        py: float = stmt.py
        pz: float = stmt.pz
        qargs: ilist.IList[ast.Bit, Any] = frame.get(stmt.qargs)
        frame.body.append(
            ast.Comment(text=f"native.Atomloss(px={px}, py={py}, pz={pz})")
        )
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([f'{q.name.id}[{q.addr}]' for q in qargs])}"
            )
        )
        return ()
