from typing import Sequence

import cirq
import numpy as np

from bloqade.qasm2.dialects.noise import TwoRowZoneModel

from .custom_gates import TwoQubitPauli
from .conflict_graph import OneZoneConflictGraph


class GeminiOneZoneNoiseModel(cirq.NoiseModel):
    """
    A Cirq-compatible noise model for a one-zone implementation of the Gemini architecture.

    This model introduces custom asymmetric depolarizing noise for both single- and two-qubit gates
    depending on whether operations are global, local, or part of a CZ interaction. Since the model assumes all
    atoms are in the entangling zone, error are applied that stem from application of Rydberg error, even for
    qubits not actively involved in a gate operation.

    Attributes:
        global_depolarization_probability (float): Depolarizing probability applied to all qubits
            during a global single-qubit gate.
        local_depolarization_probability (float): Depolarizing probability applied during local
            single-qubit gates.
        mover_pauli_probabilities (Sequence[float]): Asymmetric depolarization parameters (px, py, pz)
            applied to control qubits (movers) during a CZ gate.
        sitter_pauli_probabilities (Sequence[float]): Asymmetric depolarization parameters applied to sitters, ie.
            target qubits and idle atoms.
        paired_cz_1q_probabilities (Sequence[float]): Asymmetric 1q noise applied to both qubits in a CZ pair.
        unpaired_cz_1q_probabilities (Sequence[float]): Asymmetric 1q noise applied to idle atoms during CZ.
    """

    def __init__(
        self,
        global_depolarization_probability: float | None = None,
        local_depolarization_probability: float | None = None,
        mover_pauli_probabilities: Sequence[float] | None = None,
        sitter_pauli_probabilities: Sequence[float] | None = None,
        paired_cz_1q_probabilities: Sequence[float] | None = None,
        unpaired_cz_1q_probabilities: Sequence[float] | None = None,
    ):
        """
        Initializes the GeminiOneZoneNoiseModel with depolarization probabilities and Pauli error rates.

        All default parameters are derived from the heuristic probabilities defined in the Bloqade TwoRowZoneModel.

        Args:
            global_depolarization_probability: Noise for global single-qubit gates.
            local_depolarization_probability: Noise for local single-qubit gates.
            mover_pauli_probabilities: Asymmetric noise on control qubits in 2-qubit gates.
            sitter_pauli_probabilities: Asymmetric noise on targets and idle qubits.
            paired_cz_1q_probabilities: Noise on both qubits involved in a CZ gate.
            unpaired_cz_1q_probabilities: Noise on idle qubits during CZ operations.
        """
        bloqade_model = TwoRowZoneModel()
        if global_depolarization_probability is None:
            self.global_depolarization_probability = bloqade_model.global_errors[0] * 3
        else:
            self.global_depolarization_probability = global_depolarization_probability

        if local_depolarization_probability is None:
            self.local_depolarization_probability = bloqade_model.local_errors[0] * 3
        else:
            self.local_depolarization_probability = local_depolarization_probability

        if mover_pauli_probabilities is None:
            self.mover_pauli_probabilities = (
                bloqade_model.mover_px,
                bloqade_model.mover_py,
                bloqade_model.mover_pz,
            )
        else:
            self.mover_pauli_probabilities = mover_pauli_probabilities

        if sitter_pauli_probabilities is None:
            self.sitter_pauli_probabilities = bloqade_model.sitter_errors
        else:
            self.sitter_pauli_probabilities = sitter_pauli_probabilities

        if paired_cz_1q_probabilities is None:
            self.paired_cz_1q_probabilities = bloqade_model.cz_paired_errors
        else:
            self.paired_cz_1q_probabilities = paired_cz_1q_probabilities

        if unpaired_cz_1q_probabilities is None:
            self.unpaired_cz_1q_probabilities = bloqade_model.cz_unpaired_errors
        else:
            self.unpaired_cz_1q_probabilities = unpaired_cz_1q_probabilities

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

        gated_qubits = [op.qubits[0] for op in moment.operations]

        is_global = np.all(np.isclose(gate_params, test_params)) and set(
            gated_qubits
        ) == set(system_qubits)

        if is_global:
            gate_noise_ops = [
                cirq.depolarize(self.global_depolarization_probability).on_each(
                    gated_qubits
                )
            ]
        else:
            gate_noise_ops = [
                cirq.depolarize(self.local_depolarization_probability).on_each(
                    gated_qubits
                )
            ]

        move_noise_ops = []

        return gate_noise_ops, move_noise_ops

    def noisy_moment(self, moment: cirq.Moment, system_qubits: Sequence[cirq.Qid]):
        """
        Applies a structured noise model to a given moment depending on the type of operations it contains.

        For single-qubit moments:
            - If all gates are identical and act on all qubits, global noise is applied.
            - Otherwise, local depolarizing noise is applied per qubit.

        For two-qubit moments:
            - Applies move error to move control qubits to target qubits before the gate and again to move back after
                the gate.
            - Applies gate error to control and target qubits.
            - Adds 1q asymmetric noise to qubits that do not participate in a gate.

        Args:
            moment: A cirq.Moment containing the original quantum operations.
            system_qubits: All qubits in the system (used to determine idleness and global operations).

        Returns:
            A list of cirq.Moment objects:
                [pre-gate move noise, original moment, post-gate move noise, gate noise moment]

        Raises:
            ValueError: If the moment contains multi-qubit gates involving >2 qubits, which are unsupported.
        """
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
            # Check if the moment only contains two qubit gates
            assert np.all([len(op.qubits) == 2 for op in moment.operations])

            control_qubits = [op.qubits[0] for op in moment.operations]
            target_qubits = [op.qubits[1] for op in moment.operations]
            gated_qubits = control_qubits + target_qubits
            idle_atoms = list(set(system_qubits) - set(gated_qubits))

            move_noise_ops = [
                cirq.asymmetric_depolarize(*self.mover_pauli_probabilities).on_each(
                    control_qubits
                ),
                cirq.asymmetric_depolarize(*self.sitter_pauli_probabilities).on_each(
                    target_qubits + idle_atoms
                ),
            ]  # In this setting, we assume a 1 zone scheme where the controls move to the targets.

            gate_noise_ops = [
                cirq.asymmetric_depolarize(*self.paired_cz_1q_probabilities).on_each(
                    gated_qubits
                ),
                cirq.asymmetric_depolarize(*self.unpaired_cz_1q_probabilities).on_each(
                    idle_atoms
                ),
            ]  # In this 1 zone scheme, all unpaired atoms are in the entangling zone.
        else:
            raise ValueError(
                "Moment contains operations with more than 2 qubits, which is not supported. "
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


class GeminiOneZoneNoiseModelCorrelated(GeminiOneZoneNoiseModel):
    """
    A Cirq noise model for implementing correlated two-qubit Pauli errors in a one-zone Gemini architecture.
    """

    def __init__(
        self,
        global_depolarization_probability: float | None = None,
        local_depolarization_probability: float | None = None,
        mover_pauli_probabilities: Sequence[float] | None = None,
        sitter_pauli_probabilities: Sequence[float] | None = None,
        paired_cz_1q_probabilities: Sequence[float] | None = None,
        unpaired_cz_1q_probabilities: Sequence[float] | None = None,
        paired_cz_2q_probabilities: np.ndarray | None = None,
    ):
        """
        Initializes the GeminiOneZoneNoiseModel with depolarization probabilities and Pauli error rates.

        All default parameters are derived from the heuristic probabilities defined in the Bloqade TwoRowZoneModel.

        Args:
            global_depolarization_probability: Noise for global single-qubit gates.
            local_depolarization_probability: Noise for local single-qubit gates.
            mover_pauli_probabilities: Asymmetric noise on control qubits in 2-qubit gates.
            sitter_pauli_probabilities: Asymmetric noise on targets and idle qubits.
            paired_cz_1q_probabilities: Noise on both qubits involved in a CZ gate.
            unpaired_cz_1q_probabilities: Noise on idle qubits during CZ operations.
        """

        super().__init__(
            global_depolarization_probability,
            local_depolarization_probability,
            mover_pauli_probabilities,
            sitter_pauli_probabilities,
            paired_cz_1q_probabilities,
            unpaired_cz_1q_probabilities,
        )

        if paired_cz_2q_probabilities is None:
            # Default to no correlated errors if not provided
            self.paired_cz_2q_probabilities = np.array(
                [
                    [0.994000006, 0.000142857, 0.000142857, 0.001428570],
                    [0.000142857, 0.000142857, 0.000142857, 0.000142857],
                    [0.000142857, 0.000142857, 0.000142857, 0.000142857],
                    [0.001428570, 0.000142857, 0.000142857, 0.001428570],
                ]
            )
        else:
            if paired_cz_2q_probabilities.shape != (4, 4):
                raise ValueError(
                    "Expected a 4x4 array of probabilities for paired_cz_2q_probabilities"
                )
            self.paired_cz_2q_probabilities = paired_cz_2q_probabilities

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
                cirq.asymmetric_depolarize(*self.mover_pauli_probabilities).on_each(
                    control_qubits
                ),
                cirq.asymmetric_depolarize(*self.sitter_pauli_probabilities).on_each(
                    target_qubits + idle_atoms
                ),
            ]  # In this setting, we assume a 1 zone scheme where the controls move to the targets.

            gate_noise_ops = [
                TwoQubitPauli(self.paired_cz_2q_probabilities).on_each([c, t])
                for c, t in zip(control_qubits, target_qubits)
            ] + [
                cirq.asymmetric_depolarize(*self.unpaired_cz_1q_probabilities).on_each(
                    idle_atoms
                )
            ]
            # In this 1 zone scheme, all unpaired atoms are in the entangling zone.
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


class GeminiOneZoneNoiseModelConflictGraphMoves(GeminiOneZoneNoiseModel):
    """
    A Cirq noise model that uses a conflict graph to schedule moves in a one-zone Gemini architecture.

    Assumes that the qubits are cirq.GridQubits, such that the assignment of row, column coordinates define the initial
    geometry. An SLM site at the two qubit interaction distance is also assumed next to each cirq.GridQubit to allow
    for multiple moves before a single Rydberg pulse is applied for a parallel CZ.
    """

    def __init__(
        self,
        global_depolarization_probability: float | None = None,
        local_depolarization_probability: float | None = None,
        mover_pauli_probabilities: Sequence[float] | None = None,
        sitter_pauli_probabilities: Sequence[float] | None = None,
        paired_cz_1q_probabilities: Sequence[float] | None = None,
        unpaired_cz_1q_probabilities: Sequence[float] | None = None,
        max_parallel_movers: int = 10000,
    ):
        super().__init__(
            global_depolarization_probability,
            local_depolarization_probability,
            mover_pauli_probabilities,
            sitter_pauli_probabilities,
            paired_cz_1q_probabilities,
            unpaired_cz_1q_probabilities,
        )

        self.max_parallel_movers = max_parallel_movers

    def noisy_moment(self, moment, system_qubits):
        # Moment with original ops
        original_moment = moment
        assert np.all(
            [isinstance(q, cirq.GridQubit) for q in system_qubits]
        ), "Found a qubit that is not a GridQubit."
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
                    cirq.asymmetric_depolarize(*self.mover_pauli_probabilities).on_each(
                        control_qubits
                    ),
                    cirq.asymmetric_depolarize(
                        *self.sitter_pauli_probabilities
                    ).on_each(target_qubits + idle_atoms),
                ]

                move_moments.append(cirq.Moment(move_noise_ops))

            control_qubits = [op.qubits[0] for op in moment.operations]
            target_qubits = [op.qubits[1] for op in moment.operations]
            gated_qubits = control_qubits + target_qubits
            idle_atoms = list(set(system_qubits) - set(gated_qubits))

            gate_noise_ops = [
                cirq.asymmetric_depolarize(*self.paired_cz_1q_probabilities).on_each(
                    gated_qubits
                ),
                cirq.asymmetric_depolarize(*self.unpaired_cz_1q_probabilities).on_each(
                    idle_atoms
                ),
            ]  # In this 1 zone scheme, all unpaired atoms are in the entangling zone.
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
