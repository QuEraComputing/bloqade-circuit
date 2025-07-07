import cirq
import numpy as np


class OneZoneConflictGraph:
    """
    Assumes the qubits are specified as cirq.GridQubits with a chosen geometry.
    """

    def __init__(self, moment: cirq.Moment):
        self.moment = moment
        self.gates_in_moment = [op for op in moment.operations if len(op.qubits) == 2]
        # self.conflict_graph = self.build_conflict_graph()

    def _get_nodes(self):
        """Each qubit participating in a two-qubit gate is a node."""
        nodes = set()
        for gate in self.gates_in_moment:
            nodes.add(gate.qubits[0])
            nodes.add(gate.qubits[1])
        self.nodes = nodes

    def _get_edges(self):
        """
        Generate the edges of the conflict graph for a given moment.

        Defines self.edges as a set of tuples, where each tuple represents an edge between two qubits.
        """

        edges = set()
        for idx1, gate1 in enumerate(self.gates_in_moment):
            edges.add(gate1.qubits)
            for gate2 in self.gates_in_moment[idx1 + 1 :]:
                # X one-to-many, ie. we can't split/merge AOD tones
                if (gate1.qubits[0].row == gate2.qubits[0].row) ^ (
                    gate1.qubits[1].row == gate2.qubits[1].row
                ):
                    edges.add((gate1.qubits[0], gate2.qubits[0]))
                    edges.add((gate1.qubits[0], gate2.qubits[1]))
                    edges.add((gate1.qubits[1], gate2.qubits[0]))
                    edges.add((gate1.qubits[1], gate2.qubits[1]))
                # Y one-to-many
                if (gate1.qubits[0].col == gate2.qubits[0].col) ^ (
                    gate1.qubits[1].col == gate2.qubits[1].col
                ):
                    edges.add((gate1.qubits[0], gate2.qubits[0]))
                    edges.add((gate1.qubits[0], gate2.qubits[1]))
                    edges.add((gate1.qubits[1], gate2.qubits[0]))
                    edges.add((gate1.qubits[1], gate2.qubits[1]))
                # X ordering, ie. the ordering of AOD tones must be preserved.
                if (gate1.qubits[0].row < gate2.qubits[0].row) ^ (
                    gate1.qubits[1].row < gate2.qubits[1].row
                ):
                    edges.add((gate1.qubits[0], gate2.qubits[0]))
                    edges.add((gate1.qubits[1], gate2.qubits[1]))
                if (gate1.qubits[1].row < gate2.qubits[0].row) ^ (
                    gate1.qubits[0].row < gate2.qubits[1].row
                ):
                    edges.add((gate1.qubits[0], gate2.qubits[1]))
                    edges.add((gate1.qubits[1], gate2.qubits[0]))
                # Y ordering
                if (gate1.qubits[0].col < gate2.qubits[0].col) ^ (
                    gate1.qubits[1].col < gate2.qubits[1].col
                ):
                    edges.add((gate1.qubits[0], gate2.qubits[0]))
                    edges.add((gate1.qubits[1], gate2.qubits[1]))
                if (gate1.qubits[1].col < gate2.qubits[0].col) ^ (
                    gate1.qubits[0].col < gate2.qubits[1].col
                ):
                    edges.add((gate1.qubits[0], gate2.qubits[1]))
                    edges.add((gate1.qubits[1], gate2.qubits[0]))

        self.edges = edges

    def _get_node_degrees(self):
        deg_dict = {}
        for node in self.nodes:
            deg_dict[node] = np.sum([node in edge for edge in self.edges])
        self.degrees = deg_dict

    def get_move_schedule(self, mover_limit: int = 10000):
        """Generates a move schedule by coloring the conflict graph greedily, first coloring nodes of highest degree.

        :param mover_limit: The maximum number of qubits that can be moved in a single moment. Added as a constraint
            when coloring the conflict graph.
        :returns a dictionary of idx:[cirq.Qid] where idx indexes the move moment where the list of qubits move.
        """

        self._get_nodes()
        self._get_edges()
        self._get_node_degrees()

        self.ordered_nodes = sorted(self.degrees, key=self.degrees.get, reverse=True)

        move_schedule = {}
        colored_nodes = set()
        for node in self.ordered_nodes:
            colored = False
            for gate in self.gates_in_moment:
                if node in gate.qubits:
                    partners = set(gate.qubits)
                    partners.remove(node)
                    partner_node = list(partners)[0]
            if node in colored_nodes:
                continue
            else:
                connected_nodes = set()
                for edge in self.edges:
                    if node in edge:
                        connected_nodes.add(edge[0])
                        connected_nodes.add(edge[1])
                connected_nodes.remove(node)
                for color in move_schedule.keys():
                    has_colored_neighbor = False
                    for connected_node in connected_nodes:
                        if connected_node in move_schedule[color]:
                            has_colored_neighbor = True
                            break
                        else:
                            continue
                    mover_limit_reached = len(move_schedule[color]) >= mover_limit
                    if (has_colored_neighbor is False) and (
                        mover_limit_reached is False
                    ):
                        move_schedule[color].add(node)
                        colored = True
                        colored_nodes.add(node)
                        colored_nodes.add(partner_node)
                        break
                if colored is False:
                    move_schedule[len(move_schedule)] = {node}
                    colored = True
                    colored_nodes.add(node)
                    colored_nodes.add(partner_node)

        assert set(colored_nodes) == set(self.ordered_nodes)

        self.move_schedule = move_schedule

        return self.move_schedule
