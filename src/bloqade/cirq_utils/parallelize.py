import cirq
import numpy as np
import networkx as nx
from cirq.contrib.circuitdag.circuit_dag import CircuitDag

from .lineprog import Variable, LPProblem, Expression


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
    # Convert to CZ target gate set.
    circuit2 = cirq.optimize_for_target_gateset(circuit, gateset=cirq.CZTargetGateset())

    def reorder_check(
        op1, op2
    ):  # can reorder iff both are CZ, or intersection is empty
        if op1.gate == cirq.CZ and op2.gate == cirq.CZ:
            return True
        else:
            return len(set(op1.qubits).intersection(op2.qubits)) == 0

    # Turn into DAG
    directed: nx.DiGraph = CircuitDag.from_circuit(circuit2, can_reorder=reorder_check)
    directed2: nx.DiGraph = nx.transitive_reduction(directed)

    # ---
    # Turn into a linear program to solve
    # ---
    basis = {node: Variable() for node in directed2.nodes}
    lp = LPProblem()

    # All timesteps must be positive
    for node in directed2.nodes:
        lp.add_gez(1.0 * basis[node])

    # Add ordering constraints
    for edge in directed2.edges:
        lp.add_gez(basis[edge[1]] - basis[edge[0]] - 1)

    # Add linear objective: minimize the total time
    objective = hyperparameters["linear"] * sum(basis.values())
    if isinstance(objective, Expression):
        lp.add_linear(objective)

    # Add ABS objective: similarity wants to go together.
    for node1 in directed2.nodes:
        for node2 in directed2.nodes:
            # Auto-similarity:
            U1 = cirq.unitary(node1.val)
            U2 = cirq.unitary(node2.val)
            similar = cirq.equal_up_to_global_phase(U1, U2, atol=1e-6)
            forced_order = nx.has_path(directed, node1, node2) or nx.has_path(
                directed, node2, node1
            )
            are_disjoint = (
                len(set(node1.val.qubits).intersection(node2.val.qubits)) == 0
            )
            if similar and not forced_order and are_disjoint:
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
    solution2 = {gate: solution[basis[gate]] for gate in basis.keys()}

    # Round to integer values
    for key, val in solution2.items():
        epoch = int(np.floor(val))
        solution2[key] = epoch

    # Convert to epochs
    unique_epochs = set(solution2.values())
    epochs = {epoch: [] for epoch in unique_epochs}
    for key, val in solution2.items():
        epochs[val].append(key)
    # De-label epochs
    epochs = [epochs[ind] for ind in sorted(epochs.keys())]
    # Identify and satisfy edge coloring conflicts
    epochs_out = []
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

        best_colors: dict[tuple[cirq.LineQubit, cirq.LineQubit], int] = (
            nx.algorithms.coloring.greedy_color(linegraph, strategy="largest_first")
        )
        best_num_colors = len(set(best_colors.values()))

        strategies = [
            #'random_sequential',
            "smallest_last",
            "independent_set",
            "connected_sequential_bfs",
            "connected_sequential_dfs",
            "saturation_largest_first",
        ]
        for strategy in strategies:
            colors: dict[tuple[cirq.LineQubit, cirq.LineQubit], int] = (
                nx.algorithms.coloring.greedy_color(linegraph, strategy=strategy)
            )
            if (num_colors := len(set(colors.values()))) < best_num_colors:
                best_num_colors = num_colors
                best_colors = colors

        twoq_gates2 = [
            list(cirq.CZ(*k) for k, v in best_colors.items() if v == x)
            for x in set(best_colors.values())
        ]
        # -- end colorizer --

        # Extend the epochs.
        if len(oneq_gates) > 0:
            epochs_out.append(oneq_gates)
        epochs_out.extend(twoq_gates2)

    # Convert the epochs to a cirq circuit.
    moments = [cirq.Moment(epoch) for epoch in epochs_out]
    return cirq.Circuit(moments)
