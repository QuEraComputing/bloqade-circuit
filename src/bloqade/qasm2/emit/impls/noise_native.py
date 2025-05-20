from typing import Any

from kirin import interp
from kirin.dialects import ilist

from bloqade.noise import native
from bloqade.qasm2.parse import ast
from bloqade.qasm2.emit.gate import EmitQASM2Gate, EmitQASM2Frame


@native.dialect.register(key="emit.qasm2.gate")
class NativeNoise(interp.MethodTable):

    def _convert(self, node: ast.Bit | ast.Name) -> str:
        if isinstance(node, ast.Bit):
            return f"{node.name.id}[{node.addr}]"
        else:
            return f"{node.id}"

    @interp.impl(native.CZPauliChannel)
    def emit_czp(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: native.CZPauliChannel,
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
                text=f"native.CZPauliChannel(paired={paired}, p_ctrl=[x:{px_ctrl}, y:{py_ctrl}, z:{pz_ctrl}], p_qarg[x:{px_qarg}, y:{py_qarg}, z:{pz_qarg}])"
            )
        )
        frame.body.append(
            ast.Comment(
                text=f" -: ctrls: {', '.join([self._convert(q) for q in ctrls])}"
            )
        )
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([self._convert(q) for q in qargs])}"
            )
        )
        return ()

    @interp.impl(native.AtomLossChannel)
    def emit_loss(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: native.AtomLossChannel,
    ):
        prob: float = stmt.prob
        qargs: ilist.IList[ast.Bit, Any] = frame.get(stmt.qargs)
        frame.body.append(ast.Comment(text=f"native.Atomloss(p={prob})"))
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([self._convert(q) for q in qargs])}"
            )
        )
        return ()

    @interp.impl(native.PauliChannel)
    def emit_pauli(
        self,
        emit: EmitQASM2Gate,
        frame: EmitQASM2Frame,
        stmt: native.PauliChannel,
    ):
        px: float = stmt.px
        py: float = stmt.py
        pz: float = stmt.pz
        qargs: ilist.IList[ast.Bit, Any] = frame.get(stmt.qargs)
        frame.body.append(
            ast.Comment(text=f"native.PauliChannel(px={px}, py={py}, pz={pz})")
        )
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([self._convert(q) for q in qargs])}"
            )
        )
        return ()
