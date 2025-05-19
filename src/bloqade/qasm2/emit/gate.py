from typing import Any
from dataclasses import field, dataclass

from kirin import ir, types, interp
from kirin.dialects import py, func, ilist
from kirin.ir.dialect import Dialect as Dialect

from bloqade.types import QubitType
from bloqade.qasm2.parse import ast

from bloqade.noise import native

from .base import EmitError, EmitQASM2Base, EmitQASM2Frame


def _default_dialect_group():
    from bloqade.qasm2.groups import gate

    return gate


@dataclass
class EmitQASM2Gate(EmitQASM2Base[ast.UOp | ast.Barrier, ast.Gate]):
    keys = ["emit.qasm2.gate"]
    dialects: ir.DialectGroup = field(default_factory=_default_dialect_group)


@ilist.dialect.register(key="emit.qasm2.gate")
class Ilist(interp.MethodTable):

    @interp.impl(ilist.New)
    def emit_ilist(self, emit: EmitQASM2Gate, frame: EmitQASM2Frame, stmt: ilist.New):
        return (ilist.IList(data=frame.get_values(stmt.values)),)


@py.constant.dialect.register(key="emit.qasm2.gate")
class Constant(interp.MethodTable):

    @interp.impl(py.Constant)
    def emit_constant(
        self, emit: EmitQASM2Gate, frame: EmitQASM2Frame, stmt: py.Constant
    ):
        return (stmt.value,)


@func.dialect.register(key="emit.qasm2.gate")
class Func(interp.MethodTable):

    @interp.impl(func.Call)
    def emit_call(self, emit: EmitQASM2Gate, frame: EmitQASM2Frame, stmt: func.Call):
        raise EmitError("cannot emit dynamic call")

    @interp.impl(func.Invoke)
    def emit_invoke(
        self, emit: EmitQASM2Gate, frame: EmitQASM2Frame, stmt: func.Invoke
    ):
        ret = ()
        if len(stmt.results) == 1 and stmt.results[0].type.is_subseteq(types.NoneType):
            ret = (None,)
        elif len(stmt.results) > 0:
            raise EmitError(
                "cannot emit invoke with results, this "
                "is not compatible QASM2 gate routine"
                " (consider pass qreg/creg by argument)"
            )

        cparams, qparams = [], []
        for arg in stmt.inputs:
            if arg.type.is_subseteq(QubitType):
                qparams.append(frame.get(arg))
            else:
                cparams.append(frame.get(arg))

        frame.body.append(
            ast.Instruction(
                name=ast.Name(stmt.callee.sym_name),
                params=cparams,
                qargs=qparams,
            )
        )
        return ret

    @interp.impl(func.Lambda)
    @interp.impl(func.GetField)
    def emit_err(self, emit: EmitQASM2Gate, frame: EmitQASM2Frame, stmt):
        raise EmitError(f"illegal statement {stmt.name} for QASM2 gate routine")

    @interp.impl(func.Return)
    @interp.impl(func.ConstantNone)
    def ignore(self, emit: EmitQASM2Gate, frame: EmitQASM2Frame, stmt):
        return ()


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
                text=f"native.CZPauliChannel(paired={paired}, p_ctrl[{px_ctrl}, {py_ctrl}, {pz_ctrl}], p_qarg[{px_qarg}, {py_qarg}, {pz_qarg}])"
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
            ast.Comment(text=f"native.Atomloss(px={px}, py={py}, pz={pz})")
        )
        frame.body.append(
            ast.Comment(
                text=f" -: qargs: {', '.join([self._convert(q) for q in qargs])}"
            )
        )
        return ()
