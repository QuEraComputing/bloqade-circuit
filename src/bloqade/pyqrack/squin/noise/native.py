import random
import typing
from functools import cached_property
from dataclasses import dataclass

from kirin import interp
from kirin.dialects import ilist

from bloqade.pyqrack import QubitState, PyQrackQubit, PyQrackInterpreter
from bloqade.squin.noise.stmts import (
    QubitLoss,
    Depolarize,
    Depolarize2,
    TwoQubitPauliChannel,
    SingleQubitPauliChannel,
)
from bloqade.squin.noise._dialect import dialect as squin_noise_dialect

from ..runtime import KronRuntime, IdentityRuntime, OperatorRuntime, OperatorRuntimeABC


@dataclass(frozen=True)
class StochasticUnitaryChannelRuntime(OperatorRuntimeABC):
    operators: (
        ilist.IList[OperatorRuntimeABC, typing.Any] | tuple[OperatorRuntimeABC, ...]
    )
    probabilities: ilist.IList[float, typing.Any] | tuple[float, ...]

    @property
    def n_sites(self) -> int:
        n = self.operators[0].n_sites
        for op in self.operators[1:]:
            assert (
                op.n_sites == n
            ), "Encountered a stochastic unitary channel with operators of different size!"
        return n

    def apply(self, *qubits: PyQrackQubit, adjoint: bool = False) -> None:
        # NOTE: probabilities don't necessarily sum to 1; could be no noise event should occur
        p_no_op = 1 - sum(self.probabilities)
        if random.uniform(0.0, 1.0) < p_no_op:
            return

        selected_ops = random.choices(self.operators, weights=self.probabilities)
        for op in selected_ops:
            op.apply(*qubits, adjoint=adjoint)


@dataclass(frozen=True)
class QubitLossRuntime(OperatorRuntimeABC):
    p: float

    @property
    def n_sites(self) -> int:
        return 1

    def apply(self, qubit: PyQrackQubit, adjoint: bool = False) -> None:
        if random.uniform(0.0, 1.0) <= self.p:
            qubit.state = QubitState.Lost


@squin_noise_dialect.register(key="pyqrack")
class PyQrackMethods(interp.MethodTable):

    single_pauli_choices = ("i", "x", "y", "z")
    two_pauli_choices = (
        "II",
        "IX",
        "IY",
        "IZ",
        "XI",
        "XX",
        "XY",
        "XZ",
        "YI",
        "YX",
        "YY",
        "YZ",
        "ZI",
        "ZX",
        "ZY",
        "ZZ",
    )

    @interp.impl(Depolarize)
    def depolarize(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Depolarize
    ):
        p = frame.get(stmt.p)
        ps = (p / 3.0,) * 3
        qubits = frame.get(stmt.qubits)
        self.apply_single_qubit_pauli_error(interp, ps, qubits)

    @interp.impl(Depolarize2)
    def depolarize2(
        self, interp: PyQrackInterpreter, frame: interp.Frame, stmt: Depolarize2
    ):
        p = frame.get(stmt.p)
        ps = (p / 15.0,) * 15
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
        self.apply_single_qubit_pauli_error(interp, (px, py, pz), qubits)

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
        return (QubitLossRuntime(p),)

    @cached_property
    def single_qubit_paulis(self):
        return (OperatorRuntime("x"), OperatorRuntime("y"), OperatorRuntime("z"))

    @cached_property
    def two_qubit_paulis(self):
        paulis = (IdentityRuntime(sites=1), *self.single_qubit_paulis)
        ops: list[KronRuntime] = []
        for idx1, pauli1 in enumerate(paulis):
            for idx2, pauli2 in enumerate(paulis):
                if idx1 == idx2 == 0:
                    # NOTE: 'II'
                    continue

                ops.append(KronRuntime(pauli1, pauli2))

        return tuple(ops)

    def apply_single_qubit_pauli_error(
        self,
        interp: PyQrackInterpreter,
        ps: tuple[float, float, float],
        qubits: list[PyQrackQubit],
    ):
        pi = 1 - sum(ps)
        probs = (pi,) + ps

        assert all(0 <= x <= 1 for x in probs), "Invalid Pauli error probabilities"

        for qbit in qubits:
            which = interp.rng_state.choice(self.single_pauli_choices, p=probs)
            self.apply_pauli_error(which, qbit)

    def apply_two_qubit_pauli_error(
        self,
        interp: PyQrackInterpreter,
        ps: tuple[float, ...],
        controls: list[PyQrackQubit],
        targets: list[PyQrackQubit],
    ):
        pii = 1 - sum(ps)
        probs = (pii,) + ps
        assert all(0 <= x <= 1 for x in probs), "Invalid Pauli error probabilities"

        for control, target in zip(controls, targets):
            which = interp.rng_state.choice(self.two_pauli_choices, p=probs)
            self.apply_pauli_error(which[0], control)
            self.apply_pauli_error(which[1], target)

    def apply_pauli_error(self, which: str, qbit: PyQrackQubit):
        if not qbit.is_active() or which == "i":
            return

        getattr(qbit.sim_reg, which)(qbit.addr)
