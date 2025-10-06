from kirin import interp

from bloqade.pyqrack import PyQrackQubit, PyQrackInterpreter
from bloqade.squin.noise.stmts import (
    QubitLoss,
    CorrelatedQubitLoss,
    Depolarize,
    Depolarize2,
    TwoQubitPauliChannel,
    SingleQubitPauliChannel,
)
from bloqade.squin.noise._dialect import dialect as squin_noise_dialect


@squin_noise_dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):

    single_pauli_choices = ("i", "x", "y", "z")
    two_pauli_choices = (
        "ii",
        "ix",
        "iy",
        "iz",
        "xi",
        "xx",
        "xy",
        "xz",
        "yi",
        "yx",
        "yy",
        "yz",
        "zi",
        "zx",
        "zy",
        "zz",
    )

    @interp.impl(Depolarize)
    def depolarize(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Depolarize
    ):
        p = frame.get(stmt.p)
        ps = [p / 3.0] * 3
        qubits = frame.get(stmt.qubits)
        self.apply_single_qubit_pauli_error(interp, ps, qubits)

    @interp.impl(Depolarize2)
    def depolarize2(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Depolarize2
    ):
        p = frame.get(stmt.p)
        ps = [p / 15.0] * 15
        controls = frame.get(stmt.controls)
        targets = frame.get(stmt.targets)
        self.apply_two_qubit_pauli_error(interp, ps, controls, targets)

    @interp.impl(SingleQubitPauliChannel)
    def single_qubit_pauli_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: SingleQubitPauliChannel,
    ):
        px = frame.get(stmt.px)
        py = frame.get(stmt.py)
        pz = frame.get(stmt.pz)
        qubits = frame.get(stmt.qubits)
        self.apply_single_qubit_pauli_error(interp, [px, py, pz], qubits)

    @interp.impl(TwoQubitPauliChannel)
    def two_qubit_pauli_channel(
        self,
        interp: PyQrackInterpreter,
        frame: interp.Frame,
        stmt: TwoQubitPauliChannel,
    ):
        ps = frame.get(stmt.probabilities)
        controls = frame.get(stmt.controls)
        targets = frame.get(stmt.targets)
        self.apply_two_qubit_pauli_error(interp, ps, controls, targets)

    @interp.impl(QubitLoss)
    def qubit_loss(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: QubitLoss
    ):
        p = frame.get(stmt.p)
        qubits: list[PyQrackQubit] = frame.get(stmt.qubits)
        for qbit in qubits:
            if interp.rng_state.uniform(0.0, 1.0) <= p:
                qbit.drop()

    @interp.impl(CorrelatedQubitLoss)
    def correlated_qubit_loss(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: CorrelatedQubitLoss
    ):
        p = frame.get(stmt.p)
        qubits: list[PyQrackQubit] = frame.get(stmt.qubits)
        if interp.rng_state.uniform(0.0, 1.0) <= p:
            for qbit in qubits:
                qbit.drop()

    def apply_single_qubit_pauli_error(
        self,
        interp: PyQrackInterpreter,
        ps: list[float],
        qubits: list[PyQrackQubit],
    ):
        pi = 1 - sum(ps)
        probs = [pi] + ps

        assert all(0 <= x <= 1 for x in probs), "Invalid Pauli error probabilities"

        for qbit in qubits:
            which = interp.rng_state.choice(self.single_pauli_choices, p=probs)
            self.apply_pauli_error(which, qbit)

    def apply_two_qubit_pauli_error(
        self,
        interp: PyQrackInterpreter,
        ps: list[float],
        controls: list[PyQrackQubit],
        targets: list[PyQrackQubit],
    ):
        pii = 1 - sum(ps)
        probs = [pii] + ps
        assert all(0 <= x <= 1 for x in probs), "Invalid Pauli error probabilities"

        for control, target in zip(controls, targets):
            which = interp.rng_state.choice(self.two_pauli_choices, p=probs)
            self.apply_pauli_error(which[0], control)
            self.apply_pauli_error(which[1], target)

    def apply_pauli_error(self, which: str, qbit: PyQrackQubit):
        if not qbit.is_active() or which == "i":
            return

        getattr(qbit.sim_reg, which)(qbit.addr)
