from kirin import interp

from bloqade.squin import wire
from bloqade.pyqrack.reg import PyQrackWire, PyQrackQubit
from bloqade.pyqrack.base import PyQrackInterpreter

from .runtime import OperatorRuntimeABC


@wire.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    # @interp.impl(wire.Wrap)
    # def wrap(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: wire.Wrap):
    #     traits = frozenset({lowering.FromPythonCall(), WireTerminator()})
    #     wire: ir.SSAValue = info.argument(WireType)
    #     qubit: ir.SSAValue = info.argument(QubitType)

    @interp.impl(wire.Unwrap)
    def unwrap(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: wire.Unwrap
    ):
        q: PyQrackQubit = frame.get(stmt.qubit)
        return (PyQrackWire(q),)

    @interp.impl(wire.Apply)
    def apply(self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: wire.Apply):
        ws = stmt.inputs
        assert isinstance(ws, tuple)
        qubits: list[PyQrackQubit] = []
        for w in ws:
            assert isinstance(w, PyQrackWire)
            qubits.append(w.qubit)
        op: OperatorRuntimeABC = frame.get(stmt.operator)

        op.apply(*qubits)

        out_ws = [PyQrackWire(qbit) for qbit in qubits]
        return (out_ws,)

    @interp.impl(wire.Measure)
    def measure(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: wire.Measure
    ):
        w: PyQrackWire = frame.get(stmt.wire)
        qbit = w.qubit

        if not qbit.is_active():
            return (interp.loss_m_result,)

        res: bool = bool(qbit.sim_reg.m(qbit.addr))
        return (res,)
