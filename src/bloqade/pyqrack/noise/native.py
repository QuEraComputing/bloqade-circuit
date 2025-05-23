from typing import List

from kirin import interp

from bloqade.pyqrack import PyQrackInterpreter, reg
from bloqade.qasm2.dialects import noise


@noise.dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):
    def apply_pauli_error(
        self,
        interp: PyQrackInterpreter,
        qarg: reg.PyQrackQubit,
        px: float,
        py: float,
        pz: float,
    ):
        p = [1 - (px + py + pz), px, py, pz]

        assert all(0 <= x <= 1 for x in p), "Invalid Pauli error probabilities"

        which = interp.rng_state.choice(["i", "x", "y", "z"], p=p)

        if which == "i":
            return

        getattr(qarg.sim_reg, which)(qarg.addr)

    @interp.impl(noise.PauliChannel)
    def single_qubit_error_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: noise.PauliChannel,
    ):
        qargs: List[reg.PyQrackQubit] = frame.get(stmt.qargs)

        active_qubits = (qarg for qarg in qargs if qarg.is_active())

        for qarg in active_qubits:
            self.apply_pauli_error(interp, qarg, stmt.px, stmt.py, stmt.pz)

        return ()

    @interp.impl(noise.CZPauliChannel)
    def cz_pauli_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: noise.CZPauliChannel,
    ):

        qargs: List[reg.PyQrackQubit] = frame.get(stmt.qargs)
        ctrls: List[reg.PyQrackQubit] = frame.get(stmt.ctrls)

        if stmt.paired:
            valid_pairs = (
                (ctrl, qarg)
                for ctrl, qarg in zip(ctrls, qargs)
                if ctrl.is_active() and qarg.is_active()
            )
        else:
            valid_pairs = (
                (ctrl, qarg)
                for ctrl, qarg in zip(ctrls, qargs)
                if ctrl.is_active() ^ qarg.is_active()
            )

        for ctrl, qarg in valid_pairs:
            if ctrl.is_active():
                self.apply_pauli_error(
                    interp, ctrl, stmt.px_ctrl, stmt.py_ctrl, stmt.pz_ctrl
                )

            if qarg.is_active():
                self.apply_pauli_error(
                    interp, qarg, stmt.px_qarg, stmt.py_qarg, stmt.pz_qarg
                )

        return ()

    @interp.impl(noise.AtomLossChannel)
    def atom_loss_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: noise.AtomLossChannel,
    ):
        qargs: List[reg.PyQrackQubit] = frame.get(stmt.qargs)

        active_qubits = (qarg for qarg in qargs if qarg.is_active())

        for qarg in active_qubits:
            if interp.rng_state.uniform() <= stmt.prob:
                qarg.sim_reg.m(qarg.addr)
                qarg.drop()

        return ()
