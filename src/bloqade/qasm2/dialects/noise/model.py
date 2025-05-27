import abc
from dataclasses import field, dataclass


@dataclass(frozen=True)
class MoveNoiseModelABC(abc.ABC):
    """Abstract base class for noise based on atom movement.

    This class defines the interface for a noise model. The gate noise is calculated from the parameters
    provided in this dataclass which can be updated when inheriting from this class. The move error is
    calculated by implementing the parallel_cz_errors method which takes a set of ctrl and qarg qubits
    and returns a noise model for all the qubits. The noise model is a dictionary with the keys being the
    error rates for the qubits and the values being the list of qubits that the error rate applies to.

    Once implemented the class can be used with the NoisePass to analyze a circuit and apply the noise
    model to the circuit.

    NOTE: This model is not guaranteed to be supported long-term in bloqade. We will be
    moving towards a more general approach to noise modeling in the future.

    """

    # parameters for gate noise

    local_px: float = field(default=4.102e-04, kw_only=True)
    """The error probability for a Pauli-X error during a local single qubit gate operation."""
    local_py: float = field(default=4.102e-04, kw_only=True)
    """The error probability for a Pauli-Y error during a local single qubit gate operation."""
    local_pz: float = field(default=4.112e-04, kw_only=True)
    """The error probability for a Pauli-Z error during a local single qubit gate operation."""
    local_loss_prob: float = field(default=0.0, kw_only=True)
    """The error probability for a loss during a local single qubit gate operation."""

    local_unaddressed_px: float = field(default=2.000e-07, kw_only=True)
    """The error probability for a Pauli-X error during a local single qubit gate operation when the qubit is not addressed."""
    local_unaddressed_py: float = field(default=2.000e-07, kw_only=True)
    """The error probability for a Pauli-Y error during a local single qubit gate operation when the qubit is not addressed."""
    local_unaddressed_pz: float = field(default=1.200e-06, kw_only=True)
    """The error probability for a Pauli-Z error during a local single qubit gate operation when the qubit is not addressed."""
    local_unaddressed_loss_prob: float = field(default=0.0, kw_only=True)
    """The error probability for a loss during a local single qubit gate operation when the qubit is not addressed."""

    global_px: float = field(default=6.500e-05, kw_only=True)
    """The error probability for a Pauli-X error during a global single qubit gate operation."""
    global_py: float = field(default=6.500e-05, kw_only=True)
    """The error probability for a Pauli-Y error during a global single qubit gate operation."""
    global_pz: float = field(default=6.500e-05, kw_only=True)
    """The error probability for a Pauli-Z error during a global single qubit gate operation."""
    global_loss_prob: float = field(default=0.0, kw_only=True)
    """The error probability for a loss during a global single qubit gate operation."""

    cz_paired_gate_px: float = field(default=6.549e-04, kw_only=True)
    """The error probability for a Pauli-X error during CZ gate operation when two qubits are within blockade radius."""
    cz_paired_gate_py: float = field(default=6.549e-04, kw_only=True)
    """The error probability for a Pauli-Y error during CZ gate operation when two qubits are within blockade radius."""
    cz_paired_gate_pz: float = field(default=3.184e-03, kw_only=True)
    """The error probability for a Pauli-Z error during CZ gate operation when two qubits are within blockade radius."""
    cz_gate_loss_prob: float = field(default=0.0, kw_only=True)
    """The error probability for a loss during CZ gate operation when two qubits are within blockade radius."""

    cz_unpaired_gate_px: float = field(default=5.149e-04, kw_only=True)
    """The error probability for Pauli-X error during CZ gate operation when another qubit is not within blockade radius."""
    cz_unpaired_gate_py: float = field(default=5.149e-04, kw_only=True)
    """The error probability for Pauli-Y error during CZ gate operation when another qubit is not within blockade radius."""
    cz_unpaired_gate_pz: float = field(default=2.185e-03, kw_only=True)
    """The error probability for Pauli-Z error during CZ gate operation when another qubit is not within blockade radius."""
    cz_unpaired_loss_prob: float = field(default=0.0, kw_only=True)
    """The error probability for a loss during CZ gate operation when another qubit is not within blockade radius."""

    # parameters for move noise

    mover_px: float = field(default=8.060e-04, kw_only=True)
    """Probability of X error occurring on a moving qubit during a move operation"""
    mover_py: float = field(default=8.060e-04, kw_only=True)
    """Probability of Y error occurring on a moving qubit during a move operation"""
    mover_pz: float = field(default=2.458e-03, kw_only=True)
    """Probability of Z error occurring on a moving qubit during a move operation"""
    move_loss_prob: float = field(default=0.0, kw_only=True)
    """Probability of loss occurring on a moving qubit during a move operation"""

    sitter_px: float = field(default=3.066e-04, kw_only=True)
    """Probability of X error occurring on a stationary qubit during a move operation"""
    sitter_py: float = field(default=3.066e-04, kw_only=True)
    """Probability of Y error occurring on a stationary qubit during a move operation"""
    sitter_pz: float = field(default=4.639e-04, kw_only=True)
    """Probability of Z error occurring on a stationary qubit during a move operation"""
    sit_loss_prob: float = field(default=0.0, kw_only=True)
    """Probability of loss occurring on a stationary qubit during a move operation"""

    @property
    def cz_paired_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a CZ gate."""
        return (
            self.cz_paired_gate_px,
            self.cz_paired_gate_py,
            self.cz_paired_gate_pz,
            self.cz_gate_loss_prob,
        )

    @property
    def cz_unpaired_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a CZ gate."""
        return (
            self.cz_unpaired_gate_px,
            self.cz_unpaired_gate_py,
            self.cz_unpaired_gate_pz,
            self.cz_unpaired_loss_prob,
        )

    @property
    def local_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a local single qubit gate."""
        return (
            self.local_px,
            self.local_py,
            self.local_pz,
            self.local_loss_prob,
        )

    @property
    def local_unaddressed_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a local single qubit gate."""
        return (
            self.local_unaddressed_px,
            self.local_unaddressed_py,
            self.local_unaddressed_pz,
            self.local_unaddressed_loss_prob,
        )

    @property
    def global_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a global single qubit gate."""
        return (
            self.global_px,
            self.global_py,
            self.global_pz,
            self.global_loss_prob,
        )

    @property
    def sitter_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a move operation."""
        return (
            self.sitter_px,
            self.sitter_py,
            self.sitter_pz,
            self.sit_loss_prob,
        )

    @abc.abstractmethod
    def parallel_cz_errors(
        self, ctrls: list[int], qargs: list[int], rest: list[int]
    ) -> dict[tuple[float, float, float, float], list[int]]:
        """Takes a set of ctrls and qargs and returns a noise model for all qubits."""
        pass

    @classmethod
    def join_binary_probs(cls, p1: float, *args: float) -> float:
        """Merge the probabilities of an event happening if the event can only happen once.

        For example, finding the effective probability of losing an atom from multiple sources, since
        a qubit can only be lost once. This is done by using the formula:

        p = p1 * (1 - p2) + p2 * (1 - p1)

        applied recursively to all the probabilities in the list.

        Args:
            p1 (float): The probability of the event happening.
            arg (float): The probabilities of the event happening from other sources.

        Returns:
            float: The effective probability of the event happening.

        """
        if len(args) == 0:
            return p1
        else:
            p2 = cls.join_binary_probs(*args)
            return p1 * (1 - p2) + p2 * (1 - p1)


@dataclass(frozen=True)
class TwoRowZoneModel(MoveNoiseModelABC):
    """This model assumes that the qubits are arranged in a single storage row with a row corresponding to a gate zone below it.

    The CZ gate noise is calculated using the following heuristic: The idle error is calculated by the total duration required
    to do the move and entangle the qubits. Not every pair can be entangled at the same time, so we first deconflict the qargs
    by finding subsets in which both the ctrl and the qarg qubits are in ascending order. This breaks the pairs into
    groups that can be moved and entangled separately. We then take each group and assign each pair to a gate zone slot. The
    slots are allocated by starting from the middle of the atoms and moving outwards making sure to keep the ctrl qubits in
    ascending order. The time to move a group is calculated by finding the maximum travel distance of the qarg and ctrl qubits
    and dviding by the move speed. The total move time is the sum of all the group move times. The error rate for all the qubits
    is then calculated by using the poisson_pauli_prob function. An additional error for the pick operation is calculated by
    joining the binary probabilities of the pick operation and the move operation.

    """

    @property
    def move_errors(
        self,
    ) -> tuple[float, float, float, float]:
        """Returns the error rates for a move operation."""
        return (
            self.mover_px / 2,
            self.mover_py / 2,
            self.mover_pz / 2,
            self.move_loss_prob / 2,
        )

    def deconflict(
        self, ctrls: list[int], qargs: list[int]
    ) -> list[tuple[tuple[int, ...], tuple[int, ...]]]:
        """Return a list of groups of ctrl and qarg qubits that can be moved and entangled separately."""
        # sort by ctrl qubit first to guarantee that they will be in ascending order
        sorted_pairs = sorted(zip(ctrls, qargs))

        groups: list[list[tuple[int, int]]] = []
        # group by qarg only putting it in a group if the qarg is greater than the last qarg in the group
        # thus ensuring that the qargs are in ascending order
        while len(sorted_pairs) > 0:
            ctrl, qarg = sorted_pairs.pop(0)

            found = False
            for group in groups:
                if group[-1][1] < qarg:
                    group.append((ctrl, qarg))
                    found = True
                    break
            if not found:
                groups.append([(ctrl, qarg)])

        new_groups: list[tuple[tuple[int, ...], tuple[int, ...]]] = []

        for group in groups:
            ctrl, qarg = zip(*group)
            ctrl = tuple(ctrl)
            qarg = tuple(qarg)
            new_groups.append((ctrl, qarg))

        return new_groups

    def parallel_cz_errors(
        self, ctrls: list[int], qargs: list[int], rest: list[int]
    ) -> dict[tuple[float, float, float, float], list[int]]:
        """Apply parallel gates by moving ctrl qubits to qarg qubits."""
        groups = self.deconflict(ctrls, qargs)
        movers = ctrls + qargs
        num_moves = len(groups)
        # ignore order O(p^2) errors since they are small
        effective_move_errors = (
            self.move_errors[0] + self.sitter_errors[0] * (num_moves - 1),
            self.move_errors[1] + self.sitter_errors[1] * (num_moves - 1),
            self.move_errors[2] + self.sitter_errors[2] * (num_moves - 1),
            self.move_errors[3] + self.sitter_errors[3] * (num_moves - 1),
        )
        effective_sitter_errors = (
            self.sitter_errors[0] * num_moves,
            self.sitter_errors[1] * num_moves,
            self.sitter_errors[2] * num_moves,
            self.sitter_errors[3] * num_moves,
        )
        result = {effective_move_errors: list(movers)}
        result.setdefault(effective_sitter_errors, []).extend(rest)

        return result
