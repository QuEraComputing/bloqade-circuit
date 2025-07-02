from typing import TypeVar, Hashable, Iterable
from itertools import combinations

import cirq
import networkx as nx
from cirq.ops.gate_operation import GateOperation
from cirq.contrib.circuitdag.circuit_dag import Unique, CircuitDag

from .lineprog import Variable, LPProblem


def can_be_parallel(
    op1: cirq.GateOperation, op2: cirq.GateOperation, tol: float = 1e-14
) -> bool:
    """
    Heuristic similarity function to determine if two operations are similar enough
    to be grouped together in parallel execution.
    """
    are_disjoint = len(set(op1.qubits).intersection(op2.qubits)) == 0
    if not are_disjoint:
        return False

    # Check if both operations are CZ gates
    both_cz = op1.gate == cirq.CZ and op2.gate == cirq.CZ

    both_phased_xz = isinstance(op1.gate, cirq.PhasedXZGate) and isinstance(
        op2.gate, cirq.PhasedXZGate
    )
    equal_unitaries = cirq.equal_up_to_global_phase(
        cirq.unitary(op1.gate), cirq.unitary(op2.gate), atol=tol
    )

    return (both_phased_xz and equal_unitaries) or both_cz


def transpile(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Transpile a circuit to a native CZ gate set of {CZ, PhXZ}.
    """
    # Convert to CZ target gate set.
    circuit2 = cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset())
    missing_qubits = circuit.all_qubits() - circuit2.all_qubits()

    for qubit in missing_qubits:
        circuit2.append(
            cirq.PhasedXZGate(x_exponent=0, z_exponent=0, axis_phase_exponent=0).on(
                qubit
            )
        )

    return circuit2


def moment_similarity(
    circuit: cirq.Circuit, weight: float
) -> tuple[cirq.Circuit, dict[Hashable, float]]:
    """
    Associate every gate in each moment with a similarity group.

    Inputs:
    circuit - a cirq.Circuit to be analyzed.
    weight: float - the weight to assign to each block of gates.

    Returns:
    [0] - the cirq.Circuit with each gate annotated with topological similarity tags.
    [1] - a dictionary mapping each tag to its weight, where the key is the tag and the value is the weight.
    """
    new_moments = []
    weights = {}

    for moment_index, moment in enumerate(circuit.moments):
        tag = f"MOMENT:{moment_index}"
        new_moments.append([gate.with_tags(tag) for gate in moment.operations])
        weights[tag] = weight
    return cirq.Circuit(new_moments), weights


def block_similarity(
    circuit: cirq.Circuit, weight: float, block_id: int
) -> tuple[cirq.Circuit, dict[Hashable, float]]:
    """
    Associate every gate in a circuit with a similarity group.

    Inputs:
    circuit - a cirq.Circuit to be analyzed.
    weight: float - the weight to assign to each block of gates.

    Returns:
    [0] - the cirq.Circuit with each gate annotated with topological similarity tags.
    [1] - a dictionary mapping each tag to its weight, where the key is the tag and the value is the weight.
    """
    new_moments = []
    weights = {}
    tag = f"BLOCK:{block_id}"
    for moment in circuit.moments:
        new_moments.append([gate.with_tags(tag) for gate in moment.operations])
    weights[tag] = weight
    return cirq.Circuit(new_moments), weights


def auto_similarity(
    circuit: cirq.Circuit, weight_1q: float, weight_2q: float
) -> tuple[cirq.Circuit, dict[Hashable, float]]:
    """
    Automatically tag the circuit with topological basis group labels,
    where each group is a pair of gates that can be executed in parallel.

    Inputs:
    circuit - a cirq.Circuit to be analyzed. This should be CZ + PhaseXZGate, otherwise no annotation will occur.
    weight_1q: float - the weight to assign to single-qubit gates.
    weight_2q: float - the weight to assign to two-qubit gates.

    Returns:
    [0] - the cirq.Circuit with each gate annotated with topological similarity tags.
    [1] - a dictionary mapping each tag to its weight, where the key is the tag and the value is the weight.
    """
    flattened_circuit: list[GateOperation] = list(cirq.flatten_op_tree(circuit))
    weights = {}
    for i in range(len(flattened_circuit)):
        for j in range(i + 1, len(flattened_circuit)):
            op1 = flattened_circuit[i]
            op2 = flattened_circuit[j]
            if can_be_parallel(op1, op2):
                # Add tags to both operations
                tag = f"AUTO:{i}"
                flattened_circuit[i] = op1.with_tags(tag)
                flattened_circuit[j] = op2.with_tags(tag)
                if len(op1.qubits) == 1:
                    weights[tag] = weight_1q
                elif len(op1.qubits) == 2:
                    weights[tag] = weight_2q
                else:
                    raise RuntimeError("Unsupported gate type")
    return cirq.Circuit(flattened_circuit), weights


def no_similarity(circuit: cirq.Circuit) -> cirq.Circuit:
    """
    Removes all tags from the circuit

    Inputs:
    circuit: cirq.Circuit - the circuit to remove tags from.

    Returns:
    [0] - cirq.Circuit - the circuit with all tags removed.
    """
    new_moments = []
    for moment in circuit.moments:
        new_moments.append([gate.untagged for gate in moment.operations])
    return cirq.Circuit(new_moments)


def to_dag_circuit(circuit: cirq.Circuit, can_reorder=None) -> nx.DiGraph:
    """
    Convert a cirq.Circuit to a directed acyclic graph (DAG) representation.
    This is useful for analyzing the circuit structure and dependencies.

    Args:
        circuit: cirq.Circuit - the circuit to convert.
        can_reorder: function - a function that checks if two operations can be reordered.

    Returns:
    [0] - nx.DiGraph - the directed acyclic graph representation of the circuit.
    """

    def reorder_check(
        op1, op2
    ):  # can reorder iff both are CZ, or intersection is empty
        if op1.gate == cirq.CZ and op2.gate == cirq.CZ:
            return True
        else:
            return len(set(op1.qubits).intersection(op2.qubits)) == 0

    # Turn into DAG
    directed = CircuitDag.from_circuit(
        circuit, can_reorder=reorder_check if can_reorder is None else can_reorder
    )
    return nx.transitive_reduction(directed)


NodeType = TypeVar("NodeType")


def _get_hyperparameters(params: dict[str, float] | None) -> dict[str, float]:
    """
    Returns a dictionary of default hyperparameters for the optimization.
    """
    if params is None:
        return {
            "linear": 0.01,
            "1q": 1.0,
            "2q": 2.0,
            "tags": 0.5,
        }
    else:
        return {
            "linear": params.get("linear", 0.01),
            "1q": params.get("1q", 1.0),
            "2q": params.get("2q", 1.0),
            "tags": params.get("tags", 0.5),
        }


def solve_epochs(
    directed: nx.DiGraph,
    group_weights: dict[Hashable, float],
    hyperparameters: dict[str, float] | None = None,
) -> dict[Unique[cirq.GateOperation], float]:
    """
    Internal function to solve the epochs using linear programming.
    """

    hyperparameters = _get_hyperparameters(hyperparameters)

    basis = {node: Variable() for node in directed.nodes}

    if len(basis) == 0:
        return {}

    # ---
    # Turn into a linear program to solve
    # ---
    lp = LPProblem()

    # All timesteps must be positive
    for node in directed.nodes:
        lp.add_gez(1.0 * basis[node])

    # Add ordering constraints
    for edge in directed.edges:
        lp.add_gez(basis[edge[1]] - basis[edge[0]] - 1.0)

    all_variables = list(basis.values())
    # Add linear objective: minimize the total time
    objective = hyperparameters["linear"] * sum(all_variables[1:], all_variables[0])

    default_weight = hyperparameters["tags"]
    lp.add_linear(objective)
    # Add ABS objective: similarity wants to go together.
    for node1, node2 in combinations(directed.nodes, 2):
        # Topological (user) similarity:
        inter = set(node1.val.tags).intersection(set(node2.val.tags))
        if len(inter) > 0:
            weight = sum([group_weights.get(key, default_weight) for key in inter])
            if weight > 0:
                lp.add_abs((basis[node1] - basis[node2]) * weight)
            elif weight < 0:
                raise RuntimeError("Weights must be positive")

    solution = lp.solve()
    return {node: solution[basis[node]] for node in directed.nodes}


def generate_epochs(
    solution: dict[NodeType, float],
    tol=1e-2,
):
    """
    Internal function to generate epochs from the solution of the linear program.
    """
    sorted_gates = sorted(solution.items(), key=lambda x: x[1])
    if len(sorted_gates) == 0:
        return iter([])

    gate, latest_time = sorted_gates[0]
    current_epoch = [gate]  # Start with the first gate
    for gate, time in sorted_gates[1:]:
        if time - latest_time < tol:
            current_epoch.append(gate)
        else:
            yield current_epoch
            current_epoch = [gate]

        latest_time = time

    yield current_epoch  # Yield the last epoch


def colorize(
    epochs: Iterable[list[Unique[cirq.GateOperation]]],
):
    """
    For each epoch, separate any 1q and 2q gates, and colorize the 2q gates
    so that they can be executed in parallel without conflicts.
    Args:
        epochs: list[list[Unique[cirq.GateOperation]]] - a list of epochs, where each
            epoch is a list of gates that can be executed in parallel.

    Yields:
        list[cirq.GateOperation] - a list of lists of gates, where each
            inner list contains gates that can be executed in parallel.

    """
    for epoch in epochs:
        oneq_gates = []
        twoq_gates = []
        for gate in epoch:
            if len(gate.val.qubits) == 1:
                oneq_gates.append(gate.val)
            elif len(gate.val.qubits) == 2:
                twoq_gates.append(gate.val)
            else:
                raise RuntimeError("Unsupported gate type")

        if len(oneq_gates) > 0:
            yield oneq_gates

        # twoq_gates2 = colorizer(twoq_gates)# Inlined.
        """
        Implements an edge coloring algorithm on a set of simultaneous 2q gates,
        so that they can be done in an ordered manner so that no to gates use
        the same qubit in the same layer.
        """
        graph = nx.Graph()
        for gate in twoq_gates:
            if len(gate.qubits) != 2 and gate.gate != cirq.CZ:
                raise RuntimeError("Unsupported gate type")
            graph.add_edge(gate.qubits[0], gate.qubits[1])
        linegraph = nx.line_graph(graph)

        best_colors: dict[tuple[cirq.Qid, cirq.Qid], int] = (
            nx.algorithms.coloring.greedy_color(linegraph, strategy="largest_first")
        )
        best_num_colors = len(set(best_colors.values()))

        for strategy in (
            #'random_sequential',
            "smallest_last",
            "independent_set",
            "connected_sequential_bfs",
            "connected_sequential_dfs",
            "saturation_largest_first",
        ):
            colors: dict[tuple[cirq.Qid, cirq.Qid], int] = (
                nx.algorithms.coloring.greedy_color(linegraph, strategy=strategy)
            )
            if (num_colors := len(set(colors.values()))) < best_num_colors:
                best_num_colors = num_colors
                best_colors = colors

        twoq_gates2 = (
            list(cirq.CZ(*k) for k, v in best_colors.items() if v == x)
            for x in set(best_colors.values())
        )
        # -- end colorizer --
        yield from twoq_gates2


def parallelize(
    circuit: cirq.Circuit,
    hyperparameters: dict[str, float] | None = None,
    auto_tag: bool = True,
) -> cirq.Circuit:
    """
    Use linear programming to reorder a circuit so that it may be optimally be
    run in parallel. This is done using a DAG representation, as well as a heuristic
    similarity function to group parallelizable gates together.

    Extra topological information (similarity) can be used by tagging each gate with
    the topological basis groups that it belongs to, for example
    > circuit.append(cirq.H(qubits[0]).with_tags(1,2,3,4))
    represents that this gate is part of the topological basis groups 1,2,3, and 4.

    Inputs:
        circuit: cirq.Circuit - the static circuit to be optimized
        hyperparameters: dict[str, float] - hyperparameters for the optimization
            - "linear": float (0.01) - the linear cost of each gate
            - "1q": float (1.0)  - the quadratic cost of 1q gates
            - "2q": float (2.0)  - the quadratic cost of 2q gates
            - "tags": float (0.5) - the default weight of the topological basis.
    Returns:
        cirq.Circuit - the optimized circuit, where each moment is as parallel as possible.
          it is also broken into native CZ gate set of {CZ, PhXZ}
    """
    hyperparameters = _get_hyperparameters(hyperparameters)

    if auto_tag:
        # Transpile the circuit to a native CZ gate set.
        transpiled_circuit = transpile(circuit)
        # Annotate the circuit with topological information
        # to improve parallelization
        transpiled_circuit, group_weights = auto_similarity(
            transpiled_circuit,
            weight_1q=hyperparameters.get("1q", 1.0),
            weight_2q=hyperparameters.get("2q", 1.0),
        )
    else:
        group_weights = {}
    epochs = colorize(
        generate_epochs(
            solve_epochs(
                directed=to_dag_circuit(transpiled_circuit),
                group_weights=group_weights,
                hyperparameters=hyperparameters,
            )
        )
    )
    # Convert the epochs to a cirq circuit.
    moments = map(cirq.Moment, epochs)
    return cirq.Circuit(moments)
