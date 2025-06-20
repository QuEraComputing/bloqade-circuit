from typing import TypeVar, Iterable
from itertools import combinations

import cirq
import networkx as nx
from cirq.contrib.circuitdag.circuit_dag import Unique, CircuitDag

from .lineprog import Variable, LPProblem


def similar(
    op1: cirq.GateOperation, op2: cirq.GateOperation, tol: float = 1e-14
) -> bool:
    """
    Heuristic similarity function to determine if two operations are similar enough
    to be grouped together in parallel execution.
    """
    # Check if both operations are CZ gates
    if op1.gate == cirq.CZ and op2.gate == cirq.CZ:
        return True

    return (
        isinstance(op1.gate, cirq.PhasedXZGate)
        and isinstance(op2.gate, cirq.PhasedXZGate)
        and cirq.equal_up_to_global_phase(
            cirq.unitary(op1.gate), cirq.unitary(op2.gate), atol=tol
        )
    )


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


def to_dag_circuit(circuit: cirq.Circuit, can_reorder=None) -> nx.DiGraph:
    """
    Convert a cirq.Circuit to a directed acyclic graph (DAG) representation.
    This is useful for analyzing the circuit structure and dependencies.

    Args:
        circuit: cirq.Circuit - the circuit to convert.
        can_reorder: function - a function that checks if two operations can be reordered.

    Returns:
        nx.DiGraph - the directed acyclic graph representation of the circuit.
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


def solve_epochs(
    directed: nx.DiGraph,
    hyperparameters: dict[str, float],
) -> dict[Unique[cirq.GateOperation], float]:

    basis = {node: Variable() for node in directed.nodes}

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

    lp.add_linear(objective)
    # Add ABS objective: similarity wants to go together.
    for node1, node2 in combinations(directed.nodes, 2):
        # Auto-similarity:
        is_similar = similar(node1.val, node2.val)
        forced_order = nx.has_path(directed, node1, node2) or nx.has_path(
            directed, node2, node1
        )
        are_disjoint = len(set(node1.val.qubits).intersection(node2.val.qubits)) == 0
        if is_similar and not forced_order and are_disjoint:
            if len(node1.val.qubits) == 1:
                weight = hyperparameters["1q"]
            elif len(node1.val.qubits) == 2:
                weight = hyperparameters["2q"]
            else:
                raise RuntimeError("Unsupported gate type")
            lp.add_abs((basis[node1] - basis[node2]) * weight)

        # Topological (user) similarity:
        inter = set(node1.val.tags).intersection(set(node2.val.tags))
        if len(inter) > 0 and not forced_order and are_disjoint:
            weight = hyperparameters["tags"] * len(inter)
            lp.add_abs((basis[node1] - basis[node2]) * weight)

    solution = lp.solve()
    return {node: solution[basis[node]] for node in directed.nodes}


def generate_epochs(
    solution: dict[NodeType, float],
    tol=1e-2,
):
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
    circuit: cirq.Circuit, hyperparameters: dict[str, float] = {}
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
            - "linear": float - the linear cost of each gate
            - "1q": float - the quadratic cost of 1q gates
            - "2q": float - the quadratic cost of 2q gates
            - "tags": float - the weight of the topological basis.
    Returns:
        cirq.Circuit - the optimized circuit, where each moment is as parallel as possible.
          it is also broken into native CZ gate set of {CZ, PhXZ}
    """

    hyperparameters = {
        **{"linear": 0.01, "1q": 1.0, "2q": 1.0, "tags": 0.5},
        **hyperparameters,
    }
    epochs = colorize(
        generate_epochs(
            solve_epochs(to_dag_circuit(transpile(circuit)), hyperparameters)
        )
    )
    # Convert the epochs to a cirq circuit.
    moments = map(cirq.Moment, epochs)
    return cirq.Circuit(moments)
