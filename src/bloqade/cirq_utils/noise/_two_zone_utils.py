import copy
from typing import List, Tuple, Optional, Sequence, cast
from collections import deque

import cirq
import numpy as np
from cirq.circuits.qasm_output import QasmUGate

Slot = Tuple[int, int]  # (tuple index, position inside tuple)
Swap = Tuple[Slot, Slot]


##We make a distinction between gate and move errors. Gate errors intrinsically depend on the gate type (two qubit gates, local single qubit gates, global single qubit gates)
##Move errors are independent of the gate type, and depend on the qubit spatial layout. For our purposes, an upper bound for the move error is enough per atom move, for a given layout.
def get_qargs_from_moment(moment: cirq.Moment):
    """Returns a list of qubit arguments (qargs) from all operations in a Cirq moment.

    Args:
        moment: A cirq.Moment object.

    Returns:
        A list of tuples, where each tuple contains the qubits acted on by a gate in the moment.
    """

    list_qubs = [op.qubits for op in moment.operations]

    return list_qubs


def flatten_qargs(list_qubs: Sequence[Tuple[cirq.Qid, ...]]) -> List[cirq.Qid]:
    """Flattens a list of lists of qargs
    Args:
        list_qubs: A list of tuples of cirq.Qid objects.
    Returns:
        A flattened list of cirq.Qid objects.
    """
    return [item for tup in list_qubs for item in tup]


def qargs_to_qidxs(qargs: List[Tuple[cirq.LineQubit, ...]]) -> List[Tuple[int, ...]]:
    """
    Transforms list of qargs (tuples of cirq.LineQubit objects) into a list of tuples of integers.
    Each integer corresponds to the index of the qubit in the tuple.
    Args:
        qargs: A list of tuples of cirq.LineQubit objects.
    Returns:
        A list of tuples of integers, where each integer is the index of the qubit in the tuple.
    """
    return [tuple(x.x for x in tup) for tup in qargs]


def get_map_named_to_line_qubits(named_qubits: Sequence[cirq.NamedQubit]) -> dict:
    """
    Maps cirq.NamedQubit('q_i') objects to cirq.LineQubit(i) objects.

    Args:
        named_qubits: A list of cirq.NamedQubit objects.

    Returns:
        A dictionary mapping cirq.NamedQubit to cirq.LineQubit.
    """
    mapping = {}
    for named_qubit in named_qubits:
        # Extract the integer index from the NamedQubit name
        index = int(named_qubit.name.split("_")[1])  # Assumes format 'q_i'
        mapping[named_qubit] = cirq.LineQubit(index)
    return mapping


def numpy_complement(subset: np.ndarray, full: np.ndarray) -> np.ndarray:
    """Returns the elements in `full` that are not in `subset`.
    Args:
        subset: A numpy array of elements to exclude.
        full: A numpy array of elements from which to exclude the subset.
    Returns:
        A numpy array containing elements from `full` that are not in `subset`.
    """
    mask = ~np.isin(full, subset)
    return full[mask]


def intersect_by_structure(
    reference: List[Tuple[int, ...]], target: List[Tuple[int, ...]]
) -> List[Tuple[int, ...]]:
    target_set = set(val for t in target for val in t)
    result = []

    for tup in reference:
        filtered = tuple(val for val in tup if val in target_set)
        result.append(filtered)

    return result


def expand(
    data: Sequence[Tuple[Optional[int], ...]], capacity: int = 2
) -> List[List[Optional[int]]]:
    # Pad each tuple to have exactly `capacity` slots, using None
    return [list(t) + [None] * (capacity - len(t)) for t in data]


def flatten_with_slots(
    data: List[List[Optional[int]]],
) -> List[Tuple[Optional[int], Slot]]:
    # Create list of (value, (tuple_index, slot_index))
    return [(val, (i, j)) for i, row in enumerate(data) for j, val in enumerate(row)]


def regroup(data: List[List[Optional[int]]]) -> List[Tuple[int, ...]]:
    # Turn 2D structure back into list of sorted tuples, ignoring Nones
    return [tuple(sorted([v for v in row if v is not None])) for row in data]


def canonical_form(tuples: List[Tuple[int, ...]]) -> Tuple[Tuple[int, ...], ...]:
    # Normalize by sorting tuples and sorting the list of tuples
    return tuple(sorted(tuple(sorted(t)) for t in tuples))


def apply_swap(data: List[List[Optional[int]]], swap: Swap):
    # Swap values between two slots
    (i1, j1), (i2, j2) = swap
    data[i1][j1], data[i2][j2] = data[i2][j2], data[i1][j1]


def get_equivalent_swaps(
    source: List[Tuple[int, ...]], target: List[Tuple[int, ...]]
) -> List[Swap]:
    src = expand(source)
    tgt = expand(target)

    target_form = canonical_form(regroup(tgt))

    def config_key(state):
        return canonical_form(regroup(state))

    initial_key = config_key(src)
    visited = {initial_key}
    queue = deque([(copy.deepcopy(src), [])])  # (current state, list of swaps made)

    while queue:
        state, swaps = queue.popleft()

        if config_key(state) == target_form:
            return swaps

        flat = flatten_with_slots(state)

        for i in range(len(flat)):
            for j in range(i + 1, len(flat)):
                (_, slot_i), (_, slot_j) = flat[i], flat[j]
                apply_swap(state, (slot_i, slot_j))
                key = config_key(state)

                if key not in visited:
                    visited.add(key)
                    queue.append((copy.deepcopy(state), swaps + [(slot_i, slot_j)]))

                apply_swap(state, (slot_i, slot_j))  # Undo swap

    return []  # Should not happen if input is valid


def greedy_unique_packing(data: List[int]) -> List[List[int]]:

    remaining = deque(data)
    result = []

    while remaining:
        used = set()
        group = []
        i = 0
        length = len(remaining)

        while i < length:
            item = remaining.popleft()
            if item not in used:
                group.append(item)
                used.add(item)
            else:
                # Push it to the end for future groups
                remaining.append(item)
            i += 1

        result.append(group)

    return result


def get_swap_move_qidxs(
    swaps: List[Swap], init_qidxs: Sequence[Tuple[Optional[int], ...]]
) -> List[List[int]]:
    # Convert tuples to mutable lists
    swap_init_qidxs = expand(init_qidxs)

    moved_qidxs = []

    for (i1, j1), (i2, j2) in swaps:
        first_idx = swap_init_qidxs[i1][j1]
        sec_idx = swap_init_qidxs[i2][j2]

        if first_idx is not None:
            moved_qidxs.append(first_idx)
        if sec_idx is not None:
            moved_qidxs.append(sec_idx)

        # Perform the swap
        swap_init_qidxs[i1][j1], swap_init_qidxs[i2][j2] = sec_idx, first_idx

    return greedy_unique_packing(moved_qidxs)


def pad_with_empty_tups(
    target: List[Tuple[int, ...]], nqubs: int
) -> List[Tuple[int, ...]]:

    while len(target) < nqubs:
        target.append(())

    return target


def add_noise_to_swaps(
    swaps: List[Swap],
    init_qidxs: List[Tuple[int, ...]],
    move_noise: cirq.AsymmetricDepolarizingChannel,
    sitter_noise: cirq.AsymmetricDepolarizingChannel,
    nqubs: int,
):
    """
    Applies move noise to qubits that need to be swapped to reach a given configuration. This can be seen as the noise added to "pair-up"
    or separate qubits to reach a target configuration before the application of gates
    Args:
    swaps, array of swaps
    init_qidxs, qargs that reach the target configuration once the swaps are applied on it
    move_noise, Pauli noise channel for moves
    sitter_noise, Pauli channel for sitter noise
    nqubs, the circuit width
    """
    built_circuit = cirq.Circuit()
    nqubs_idxs = np.arange(nqubs)

    batches_move_qidxs = get_swap_move_qidxs(swaps, init_qidxs)

    for batch in batches_move_qidxs:
        built_moment = cirq.Moment()
        non_mov_qidxs = numpy_complement(np.array(batch), nqubs_idxs)

        for i in range(len(batch)):
            built_moment += move_noise(cirq.LineQubit(batch[i]))
        for j in range(len(non_mov_qidxs)):
            built_moment += sitter_noise(cirq.LineQubit(non_mov_qidxs[j]))

        built_circuit.append(built_moment)

    # built_circuit.append(built_moment)

    return built_circuit


#############################################


def get_gate_error_channel(
    moment: cirq.Moment,
    sq_loc_rates: np.ndarray,
    sq_glob_rates: np.ndarray,
    two_qubit_pauli: cirq.Gate,
    unp_cz_rates: np.ndarray,
    nqubs: int,
):
    """Applies gate errors to the circuit

    Args:
        moment: A cirq.Moment object.
        sq_loc_rates: single local qubit rotation Pauli noise channel parameters (px, py, pz)
        sq_glob_rates: single global qubit rotation Pauli noise channel parameters (px,py,pz)
        two_qubit_pauli: correlated two-qubit noise channel (ctrl_px, ctrl_py,ctrl_pz,tar_px,tar_py,tar_pz)
        unp_cz_rates: Pauli noise channel parameters for qubits in the gate zone and outside blockade radius
        nqubs: total number of qubits
    Returns:
        A new cirq.Moment object with the gate errors applied.
    """
    # Check for the moment (layer) layout: global single qubit gates, or mixture of single qubit gates and two qubit gates

    gates_in_layer = extract_u3_and_cz_qargs(moment)
    new_moments = cirq.Circuit()

    if gates_in_layer["cz"] == []:

        if gates_in_layer["u3"] == []:
            print(
                "Warning: Assumed Only single qubit gates in the layer, but there are no single qubit gates"
            )

        if all(
            np.all(np.isclose(element, gates_in_layer["angles"][0]))
            for element in gates_in_layer["angles"]
        ) and nqubs == len(gates_in_layer["u3"]):
            pauli_channel = cirq.AsymmetricDepolarizingChannel(
                p_x=sq_glob_rates[0], p_y=sq_glob_rates[1], p_z=sq_glob_rates[2]
            )

            for qub in gates_in_layer["u3"]:

                # new_moment = new_moment +pauli_channel(qub[0])
                new_moments.append(pauli_channel(qub[0]))
        else:
            pauli_channel = cirq.AsymmetricDepolarizingChannel(
                p_x=sq_loc_rates[0], p_y=sq_loc_rates[1], p_z=sq_loc_rates[2]
            )
            for qub in gates_in_layer["u3"]:

                # new_moment = new_moment + pauli_channel(qub[0])
                new_moments.append(pauli_channel(qub[0]))

    else:
        # there is at least one CZ gate...
        loc_rot_pauli_channel = cirq.AsymmetricDepolarizingChannel(
            p_x=sq_loc_rates[0], p_y=sq_loc_rates[1], p_z=sq_loc_rates[2]
        )
        unp_cz_pauli_channel = cirq.AsymmetricDepolarizingChannel(
            p_x=unp_cz_rates[0], p_y=unp_cz_rates[1], p_z=unp_cz_rates[2]
        )

        # apply correlated noise to paired qubits
        for qub in gates_in_layer["cz"]:
            new_moments.append(two_qubit_pauli.on(qub[0], qub[1]))

        for qub in gates_in_layer["u3"]:
            new_moments.append(
                unp_cz_pauli_channel(qub[0])
            )  ###qubits in the gate zone get unpaired_cz error
            new_moments.append(loc_rot_pauli_channel(qub[0]))

    return new_moments


def add_move_and_sitter_channels(
    ref_qargs: Sequence[Tuple[cirq.Qid, ...]] | None,
    tar_qargs: Sequence[Tuple[cirq.Qid, ...]],
    built_moment: cirq.Moment,
    qub_reg: Sequence[cirq.Qid],
    sitter_pauli_channel: cirq.Gate,
    move_pauli_channel: cirq.Gate,
):
    """
    Adds move and sitter noise channels according to the following rule: all the qargs in ref_moment that
    are absent in tar_moment get a move error and the rest of qubits in the qub_reg get a sitter error. It also returns a boolean variable
    that determines whether move noise was added

    Args:
        ref_qargs: reference qargs
        tar_qargs: moment to make the comparison with
        built_moment: the moment to which we append the noise channels
        qub_reg: the qubit register
        sitter_pauli channel: the parameterized sitter channel
        move_pauli_channel: the parameterized move_pauli channel
    """

    # Faltten ref_qargs and ref_qargs for purposes of identifying how to apply noise:
    flat_tar_qargs = flatten_qargs(tar_qargs)

    if ref_qargs is None:  # we are adding noise to the beginning of circuit...

        flat_ref_qargs = flatten_qargs(tar_qargs)

        bool_list = [k not in flat_tar_qargs for k in flat_ref_qargs]

    else:
        flat_ref_qargs = flatten_qargs(ref_qargs)

        bool_list = [k in flat_tar_qargs for k in flat_ref_qargs]

    rem_qubs = []

    for i in range(len(flat_ref_qargs)):
        if not bool_list[i]:
            rem_qubs.append(flat_ref_qargs[i])
            built_moment += move_pauli_channel(flat_ref_qargs[i])

    if len(rem_qubs) >= 1:

        for k in range(len(qub_reg)):
            if qub_reg[k] not in rem_qubs:
                built_moment += sitter_pauli_channel(qub_reg[k])

        return built_moment, True
    else:
        return built_moment, False


def get_move_error_channel_two_zoned(
    curr_moment: cirq.Moment,
    prev_moment: cirq.Moment | None,
    move_rates: np.ndarray,
    sitter_rates: np.ndarray,
    nqubs: int,
):
    """Applies move noise channels to a cirq moment (curr_moment), depending on the qargs of another one (prev_moment)
    returns a circuit that contains the noisy moments

    Args:
        curr_moment: A cirq.Moment object.
        prev_moment: A cirq.Moment object
        move_rates: Pauli noise channel parameters for atom moves (px,py,pz)
        sitter_rates: probailities of sitter noise (px,py,pz)
        nqubs: total number of qubits (width of the circuit)
    Returns:
        A circuit with atom move channels appended
    """

    curr_qargs = get_qargs_from_moment(curr_moment)

    move_pauli_channel = cirq.AsymmetricDepolarizingChannel(
        p_x=move_rates[0], p_y=move_rates[1], p_z=move_rates[2]
    )
    sitter_pauli_channel = cirq.AsymmetricDepolarizingChannel(
        p_x=sitter_rates[0], p_y=sitter_rates[1], p_z=sitter_rates[2]
    )
    qub_reg = [cirq.LineQubit(i) for i in range(nqubs)]

    if prev_moment is None:
        ###Initial layer of circuit, all qubits in the first layer get move error, rest get sitter
        new_moment = cirq.Moment()
        dumb_circ = cirq.Circuit()
        new_moment, _ = add_move_and_sitter_channels(
            prev_moment,
            curr_qargs,
            new_moment,
            qub_reg,
            sitter_pauli_channel,
            move_pauli_channel,
        )
        dumb_circ.append(new_moment)

    else:
        prev_qargs = get_qargs_from_moment(prev_moment)
        # We follow this convention: 1) all qargs in previous moment that need to be removed from gate zone
        # get move error, the rest get sitter error. 2) after this, all qargs that need to be brought to
        # gate zone get move error, the rest get sitter error.
        new_moment = cirq.Moment()
        dumb_circ = cirq.Circuit()
        new_moment, first_move_added = add_move_and_sitter_channels(
            prev_qargs,
            curr_qargs,
            new_moment,
            qub_reg,
            sitter_pauli_channel,
            move_pauli_channel,
        )
        dumb_circ.append(new_moment)

        new_moment = cirq.Moment()
        new_moment, second_move_added = add_move_and_sitter_channels(
            curr_qargs,
            prev_qargs,
            new_moment,
            qub_reg,
            sitter_pauli_channel,
            move_pauli_channel,
        )
        dumb_circ.append(new_moment)
        # Once the noise channels to have the target qargs in the gate zone are added, we include an additional move error
        # to reconfigure

        # Find the initial and final qarg configuration in the previous and current moments...
        prev_qidxs = qargs_to_qidxs(prev_qargs)
        curr_qidxs = qargs_to_qidxs(curr_qargs)

        intsc_rev = intersect_by_structure(prev_qidxs, curr_qidxs)
        intsc_fow = intersect_by_structure(curr_qidxs, prev_qidxs)

        # get swaps that render previous configuration to current...
        swaps = get_equivalent_swaps(
            pad_with_empty_tups(intsc_rev, nqubs), pad_with_empty_tups(intsc_fow, nqubs)
        )

        # apply noise channels...

        swap_noise_circ = add_noise_to_swaps(
            swaps, intsc_rev, move_pauli_channel, sitter_pauli_channel, nqubs
        )
        dumb_circ.append(swap_noise_circ)

    return dumb_circ


def extract_u3_and_cz_qargs(moment: cirq.Moment):
    """
    Extracts the qubit arguments (qargs) for u3 and CZ gates from a Cirq moment,
    and the angle parameters of the u3 gates.

    Args:
        moment: A cirq.Moment object containing only u3 and CZ gates.

    Returns:
        A dictionary with keys 'u3', 'cz', and 'angles', where:
        - 'u3' maps to a list of qargs (tuples of qubits) for u3 OR PhXZ gates.
        - 'cz' maps to a list of qargs (tuples of qubits) for CZ gates.
        - 'angles' maps to a list of angle parameters (tuples) for the u3 gates.
    """
    result = {"u3": [], "cz": [], "angles": []}

    for op in moment.operations:

        if isinstance(op.gate, QasmUGate):  # u3 gate in Cirq
            result["u3"].append(op.qubits)
            # Extract angle parameters (x_exponent, z_exponent, axis_phase_exponent)
            gate = cast(QasmUGate, op.gate)
            angles = (gate.theta, gate.phi, gate.lmda)
            result["angles"].append(angles)
        elif isinstance(op.gate, cirq.PhasedXZGate):  # CZ gate in Cirq
            result["u3"].append(op.qubits)
            # Extract angle parameters (x_exponent, z_exponent, axis_phase_exponent)
            gate = cast(cirq.PhasedXZGate, op.gate)
            angles = (gate.x_exponent, gate.z_exponent, gate.axis_phase_exponent)

            result["angles"].append(angles)
        elif isinstance(op.gate, cirq.CZPowGate):  # CZ gate in Cirq

            result["cz"].append(op.qubits)

    return result
