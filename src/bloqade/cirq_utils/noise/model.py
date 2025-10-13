from typing import Iterable, Sequence, cast
from dataclasses import dataclass

import cirq
import numpy as np

from bloqade.qasm2.dialects.noise import MoveNoiseModelABC

from . import _two_zone_utils
from ..parallelize import parallelize
from .conflict_graph import OneZoneConflictGraph


def _default_cz_paired_correlated_rates() -> dict:
    rates = np.array(
        [
            [9.93492628e-01, 2.27472300e-04, 2.27472300e-04, 1.51277730e-03],
            [2.27472300e-04, 1.42864200e-04, 1.42864200e-04, 1.43082900e-04],
            [2.27472300e-04, 1.42864200e-04, 1.42864200e-04, 1.43082900e-04],
            [1.51277730e-03, 1.43082900e-04, 1.43082900e-04, 1.42813990e-03],
        ]
    )

    return correlated_noise_array_to_dict(noise_rates=rates)


def correlated_noise_array_to_dict(noise_rates: np.ndarray) -> dict:
    paulis = ("I", "X", "Y", "Z")
    error_probabilities = {}
    for idx1, p1 in enumerate(paulis):
        for idx2, p2 in enumerate(paulis):
            probability = noise_rates[idx1, idx2]

            if probability > 0:
                key = p1 + p2
                error_probabilities[key] = probability

    return error_probabilities


@dataclass(frozen=True)
class GeminiNoiseModelABC(cirq.NoiseModel, MoveNoiseModelABC):
    """Abstract base class for all Gemini noise models."""

    check_input_circuit: bool = True
    """Determine whether or not to verify that the circuit only contains native gates.

    **Caution**: Disabling this for circuits containing non-native gates may lead to incorrect results!

    """

    cz_paired_correlated_rates: np.ndarray | None = None
    """The correlated CZ error rates as a 4x4 array."""

    cz_paired_error_probabilities: dict | None = None
    """The correlated CZ error rates as a dictionary"""

    def __post_init__(self):
        if (
            self.cz_paired_correlated_rates is None
            and self.cz_paired_error_probabilities is None
        ):
            # NOTE: no input, set to default value; weird setattr for frozen dataclass
            object.__setattr__(
                self,
                "cz_paired_error_probabilities",
                _default_cz_paired_correlated_rates(),
            )
        elif (
            self.cz_paired_correlated_rates is not None
            and self.cz_paired_correlated_rates is None
        ):

            if self.cz_paired_correlated_rates.shape != (4, 4):
                raise ValueError(
                    "Expected a 4x4 array of probabilities for cz_paired_correlated_rates"
                )

            # NOTE: convert array to dict
            object.__setattr__(
                self,
                "cz_paired_error_probabilities",
                correlated_noise_array_to_dict(self.cz_paired_correlated_rates),
            )
        elif (
            self.cz_paired_correlated_rates is not None
            and self.cz_paired_correlated_rates is not None
        ):
            raise ValueError(
                "Received both `cz_paired_correlated_rates` and `cz_paired_correlated_rates` as input. This is ambiguous, please only set one."
            )

    @staticmethod
    def validate_moments(moments: Iterable[cirq.Moment]):
        allowed_target_gates: frozenset[cirq.GateFamily] = cirq.CZTargetGateset().gates

        for moment in moments:
            for operation in moment:
                if not isinstance(operation, cirq.Operation):
                    continue

                gate = operation.gate
                for allowed_family in allowed_target_gates:
                    if gate in allowed_family:
                        break
                else:
                    raise ValueError(
                        f"Noise model only supported for circuits containing native gates part of the CZTargetGateSet, but encountered {operation} in moment {moment}! "
                        "To solve this error you can either use the `bloqade.cirq_utils.noise.transform` method setting `to_target_gateset = True` "
                        "or use the `bloqade.cirq_utils.transpile` method to convert the circuit before applying the noise model."
                    )

    def parallel_cz_errors(
        self, ctrls: list[int], qargs: list[int], rest: list[int]
    ) -> dict[tuple[float, float, float, float], list[int]]:
        raise NotImplementedError(
            "This noise model doesn't support rewrites on bloqade kernels, but should be used with cirq."
        )

    @property
    def mover_pauli_rates(self) -> tuple[float, float, float]:
        return (self.mover_px, self.mover_py, self.mover_pz)

    @property
    def sitter_pauli_rates(self) -> tuple[float, float, float]:
        return (self.sitter_px, self.sitter_py, self.sitter_pz)

    @property
    def global_pauli_rates(self) -> tuple[float, float, float]:
        return (self.global_px, self.global_py, self.global_pz)

    @property
    def local_pauli_rates(self) -> tuple[float, float, float]:
        return (self.local_px, self.local_py, self.local_pz)

    @property
    def cz_paired_pauli_rates(self) -> tuple[float, float, float]:
        return (
            self.cz_paired_gate_px,
            self.cz_paired_gate_py,
            self.cz_paired_gate_pz,
        )

    @property
    def cz_unpaired_pauli_rates(self) -> tuple[float, float, float]:
        return (
            self.cz_unpaired_gate_px,
            self.cz_unpaired_gate_py,
            self.cz_unpaired_gate_pz,
        )

    @property
    def two_qubit_pauli(self) -> cirq.AsymmetricDepolarizingChannel:
        # NOTE: if this was None it would error when instantiating self
        # quiet the linter for the copy below
        error_probabilities = cast(dict, self.cz_paired_error_probabilities)

        # NOTE: copy dict since cirq modifies it in-place somewhere
        return cirq.AsymmetricDepolarizingChannel(
            error_probabilities=error_probabilities.copy()
        )


@dataclass(frozen=True)
class GeminiOneZoneNoiseModel(GeminiNoiseModelABC):
    """
    A Cirq-compatible noise model for a one-zone implementation of the Gemini architecture.

    This model introduces custom asymmetric depolarizing noise for both single- and two-qubit gates
    depending on whether operations are global, local, or part of a CZ interaction. Since the model assumes all
    atoms are in the entangling zone, errors are applied that stem from application of Rydberg error, even for
    qubits not actively involved in a gate operation.

    Note, that the noise applied to entangling pairs is correlated.
    """

    parallelize_circuit: bool = False

    def _single_qubit_moment_noise_ops(
        self, moment: cirq.Moment, system_qubits: Sequence[cirq.Qid]
    ) -> tuple[list, list]:
        """
        Helper function to determine the noise operations for a single qubit moment.

        :param moment: The current cirq.Moment being evaluated.
        :param system_qubits: All qubits in the circuit.
        :return: A tuple containing gate noise operations and move noise operations for the given moment.
        """
        # Check if the moment only contains single qubit gates
        assert np.all([len(op.qubits) == 1 for op in moment.operations])
        # Check if single qubit gate is global or local
        gate_params = [
            [op.gate.axis_phase_exponent, op.gate.x_exponent, op.gate.z_exponent]
            for op in moment.operations
        ]
        gate_params = np.array(gate_params)

        test_params = [
            [
                moment.operations[0].gate.axis_phase_exponent,
                moment.operations[0].gate.x_exponent,
                moment.operations[0].gate.z_exponent,
            ]
            for _ in moment.operations
        ]
        test_params = np.array(test_params)

        gated_qubits = [
            op.qubits[0]
            for op in moment.operations
            if not (
                np.isclose(op.gate.x_exponent, 0) and np.isclose(op.gate.z_exponent, 0)
            )
        ]

        is_global = np.all(np.isclose(gate_params, test_params)) and set(
            gated_qubits
        ) == set(system_qubits)

        if is_global:
            p_x = self.global_px
            p_y = self.global_py
            p_z = self.global_pz
        else:
            p_x = self.local_px
            p_y = self.local_py
            p_z = self.local_pz

        if p_x == p_y == p_z:
            gate_noise_op = cirq.depolarize(p_x + p_y + p_z).on_each(gated_qubits)
        else:
            gate_noise_op = cirq.asymmetric_depolarize(
                p_x=p_x, p_y=p_y, p_z=p_z
            ).on_each(gated_qubits)

        return [gate_noise_op], []

    def noisy_moment(self, moment, system_qubits):
        # Moment with original ops
        original_moment = moment

        # Check if the moment is empty
        if len(moment.operations) == 0:
            move_noise_ops = []
            gate_noise_ops = []
        # Check if the moment contains 1-qubit gates or 2-qubit gates
        elif len(moment.operations[0].qubits) == 1:
            gate_noise_ops, move_noise_ops = self._single_qubit_moment_noise_ops(
                moment, system_qubits
            )
        elif len(moment.operations[0].qubits) == 2:
            control_qubits = [op.qubits[0] for op in moment.operations]
            target_qubits = [op.qubits[1] for op in moment.operations]
            gated_qubits = control_qubits + target_qubits
            idle_atoms = list(set(system_qubits) - set(gated_qubits))

            move_noise_ops = [
                cirq.asymmetric_depolarize(*self.mover_pauli_rates).on_each(
                    control_qubits
                ),
                cirq.asymmetric_depolarize(*self.sitter_pauli_rates).on_each(
                    target_qubits + idle_atoms
                ),
            ]  # In this setting, we assume a 1 zone scheme where the controls move to the targets.

            # Add correlated noise channels for entangling pairs
            two_qubit_pauli = self.two_qubit_pauli
            gate_noise_ops = [
                two_qubit_pauli.on_each([c, t])
                for c, t in zip(control_qubits, target_qubits)
            ]

            # In this 1 zone scheme, all unpaired atoms are in the entangling zone.
            idle_depolarize = cirq.asymmetric_depolarize(
                *self.cz_unpaired_pauli_rates
            ).on_each(idle_atoms)

            gate_noise_ops.append(idle_depolarize)
        else:
            raise ValueError(
                "Moment contains operations with more than 2 qubits, which is not supported."
                "Correlated measurements should be added after the noise model is applied."
            )
        if move_noise_ops == []:
            move_noise_moments = []
        else:
            move_noise_moments = [cirq.Moment(move_noise_ops)]
        gate_noise_moment = cirq.Moment(gate_noise_ops)

        return [
            *move_noise_moments,
            original_moment,
            gate_noise_moment,
            *move_noise_moments,
        ]

    def noisy_moments(
        self, moments: Iterable[cirq.Moment], system_qubits: Sequence[cirq.Qid]
    ) -> Sequence[cirq.OP_TREE]:
        """Adds possibly stateful noise to a series of moments.

        Args:
            moments: The moments to add noise to.
            system_qubits: A list of all qubits in the system.

        Returns:
            A sequence of OP_TREEEs, with the k'th tree corresponding to the
            noisy operations for the k'th moment.
        """

        if self.check_input_circuit:
            self.validate_moments(moments)

        # Split into moments with only 1Q and 2Q gates
        moments_1q = [
            cirq.Moment([op for op in moment.operations if len(op.qubits) == 1])
            for moment in moments
        ]
        moments_2q = [
            cirq.Moment([op for op in moment.operations if len(op.qubits) == 2])
            for moment in moments
        ]

        assert len(moments_1q) == len(moments_2q)

        interleaved_moments = []
        for idx, moment in enumerate(moments_1q):
            interleaved_moments.append(moment)
            interleaved_moments.append(moments_2q[idx])

        interleaved_circuit = cirq.Circuit.from_moments(*interleaved_moments)

        # Combine subsequent 1Q gates
        compressed_circuit = cirq.merge_single_qubit_moments_to_phxz(
            interleaved_circuit
        )
        if self.parallelize_circuit:
            compressed_circuit = parallelize(compressed_circuit)

        return self._noisy_moments_impl_moment(
            compressed_circuit.moments, system_qubits
        )


@dataclass(frozen=True)
class GeminiOneZoneNoiseModelConflictGraphMoves(GeminiOneZoneNoiseModel):
    """
    A Cirq noise model that uses a conflict graph to schedule moves in a one-zone Gemini architecture.

    Assumes that the qubits are cirq.GridQubits, such that the assignment of row, column coordinates define the initial
    geometry. An SLM site at the two qubit interaction distance is also assumed next to each cirq.GridQubit to allow
    for multiple moves before a single Rydberg pulse is applied for a parallel CZ.
    """

    max_parallel_movers: int = 10000

    def noisy_moment(self, moment, system_qubits):
        # Moment with original ops
        original_moment = moment
        assert np.all([isinstance(q, cirq.GridQubit) for q in system_qubits]), (
            "Found a qubit that is not a GridQubit. In order for the conflict graph to know the qubit geometry, "
            "all qubits in the circuit must be defined as cirq.GridQubit objects."
        )
        # Check if the moment is empty
        if len(moment.operations) == 0:
            move_moments = []
            gate_noise_ops = []
        # Check if the moment contains 1-qubit gates or 2-qubit gates
        elif len(moment.operations[0].qubits) == 1:
            gate_noise_ops, _ = self._single_qubit_moment_noise_ops(
                moment, system_qubits
            )
            move_moments = []
        elif len(moment.operations[0].qubits) == 2:
            cg = OneZoneConflictGraph(moment)
            schedule = cg.get_move_schedule(mover_limit=self.max_parallel_movers)
            move_moments = []
            for move_moment_idx, movers in schedule.items():
                control_qubits = list(movers)
                target_qubits = list(
                    set(
                        [op.qubits[0] for op in moment.operations]
                        + [op.qubits[1] for op in moment.operations]
                    )
                    - movers
                )
                gated_qubits = control_qubits + target_qubits
                idle_atoms = list(set(system_qubits) - set(gated_qubits))

                move_noise_ops = [
                    cirq.asymmetric_depolarize(*self.mover_pauli_rates).on_each(
                        control_qubits
                    ),
                    cirq.asymmetric_depolarize(*self.sitter_pauli_rates).on_each(
                        target_qubits + idle_atoms
                    ),
                ]

                move_moments.append(cirq.Moment(move_noise_ops))

            control_qubits = [op.qubits[0] for op in moment.operations]
            target_qubits = [op.qubits[1] for op in moment.operations]
            gated_qubits = control_qubits + target_qubits
            idle_atoms = list(set(system_qubits) - set(gated_qubits))

            # Add correlated noise channels for entangling pairs
            two_qubit_pauli = self.two_qubit_pauli
            gate_noise_ops = [
                two_qubit_pauli.on(c, t) for c, t in zip(control_qubits, target_qubits)
            ]

            # In this 1 zone scheme, all unpaired atoms are in the entangling zone.
            gate_noise_ops.append(
                cirq.asymmetric_depolarize(*self.cz_unpaired_pauli_rates).on_each(
                    idle_atoms
                ),
            )
        else:
            raise ValueError(
                "Moment contains operations with more than 2 qubits, which is not supported."
                "Correlated measurements should be added after the noise model is applied."
            )

        gate_noise_moment = cirq.Moment(gate_noise_ops)

        return [
            *move_moments,
            original_moment,
            gate_noise_moment,
            *(move_moments[::-1]),
        ]


@dataclass(frozen=True)
class GeminiTwoZoneNoiseModel(GeminiNoiseModelABC):
    def noisy_moments(
        self, moments: Iterable[cirq.Moment], system_qubits: Sequence[cirq.Qid]
    ) -> Sequence[cirq.OP_TREE]:
        """Adds possibly stateful noise to a series of moments.

        Args:
            moments: The moments to add noise to.
            system_qubits: A list of all qubits in the system.

        Returns:
            A sequence of OP_TREEEs, with the k'th tree corresponding to the
            noisy operations for the k'th moment.
        """

        if self.check_input_circuit:
            self.validate_moments(moments)

        moments = list(moments)

        if len(moments) == 0:
            return []

        nqubs = len(system_qubits)
        noisy_moment_list = []

        prev_moment: cirq.Moment | None = None

        # TODO: clean up error getters so they return a list moments rather than circuits
        for i in range(len(moments)):
            noisy_moment_list.extend(
                [
                    moment
                    for moment in _two_zone_utils.get_move_error_channel_two_zoned(
                        moments[i],
                        prev_moment,
                        np.array(self.mover_pauli_rates),
                        np.array(self.sitter_pauli_rates),
                        nqubs,
                    ).moments
                    if len(moment) > 0
                ]
            )

            noisy_moment_list.append(moments[i])

            noisy_moment_list.extend(
                [
                    moment
                    for moment in _two_zone_utils.get_gate_error_channel(
                        moments[i],
                        np.array(self.local_pauli_rates),
                        np.array(self.global_pauli_rates),
                        self.two_qubit_pauli,
                        np.array(self.cz_unpaired_pauli_rates),
                        nqubs,
                    ).moments
                    if len(moment) > 0
                ]
            )

            prev_moment = moments[i]

        return noisy_moment_list
