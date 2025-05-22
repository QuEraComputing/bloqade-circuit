from collections import Counter
import cirq
import networkx as nx

import numpy as np
from typing import Union
import dataclasses

import scipy
import scipy.sparse
from qpsolvers import solve_qp


class Variable:
    def __add__(self, other:Union["Variable","Expression",float,int]) -> "Expression":
        if isinstance(other, Variable):
            return Expression({self: 1}) + Expression({other: 1})
        elif isinstance(other, Expression):
            return Expression({self: 1}) + other
        elif isinstance(other, (float, int)):
            return Expression({self: 1}) + Expression({None: other})
        else:
            raise TypeError(f"Cannot add {type(other)} to Variable")

    def __radd__(self, left: float | int) -> "Expression":
        return self.__add__(left)

    def __sub__(self, other:Union["Variable","Expression",float,int]) -> "Expression":
        if isinstance(other, Variable):
            return Expression({self: 1}) - Expression({other: 1})
        elif isinstance(other, Expression):
            return Expression({self: 1}) - other
        elif isinstance(other, (float, int)):
            return Expression({self: 1}) - Expression({None: other})
        else:
            raise TypeError(f"Cannot subtract {type(other)} from Variable")
    def __rsub__(self, left: float | int) -> "Expression":
        return self.__sub__(left)
    def __neg__(self) -> "Expression":
        return 0 - self
    def __mul__(self, factor: float | int) -> "Expression":
        if not isinstance(factor, (float, int)):
            raise TypeError("Cannot multiply by non-numeric type")
        return Expression({self: factor})
    def __rmul__(self, factor: float | int) -> "Expression":
        return self.__mul__(factor)
    def __truediv__(self, factor: float | int) -> "Expression":
        if not isinstance(factor, (float, int)):
            raise TypeError("Cannot divide by non-numeric type")
        return Expression({self: 1 / factor})
        



@dataclasses.dataclass(frozen=True)
class Expression:
    coeffs: dict[Variable | None, float]
    
    def get(self, key: Variable | None) -> float:
        if key in self.coeffs:
            return self.coeffs[key]
        else:
            return 0
        
    def __getitem__(self, key: Variable | None) -> float:
        return self.get(key)
    
    def __add__(self, other: Union["Expression", "Variable", float, int]) -> "Expression":
        if isinstance(other, Variable):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[other] = coeff.get(other, 0) + 1
            return Expression(coeffs=coeff)
        elif isinstance(other, Expression):
            coeff = {}
            for key in set(self.coeffs.keys()).union(other.coeffs.keys()):
                coeff[key] = self.coeffs.get(key, 0) + other.coeffs.get(key, 0)
            return Expression(coeffs=coeff)
        elif isinstance(other, (float, int)):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[None] = coeff.get(None, 0) + other
            return Expression(coeffs=coeff)
        

    def __radd__(self, left: float | int) -> "Expression":
        return self.__add__(left)

    def __sub__(self, other: Union["Expression", "Variable", float, int]) -> "Expression":
        if isinstance(other, Variable):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[other] = coeff.get(other, 0) - 1
            return Expression(coeffs=coeff)
        elif isinstance(other, Expression):
            coeff = {}
            for key in set(self.coeffs.keys()).union(other.coeffs.keys()):
                coeff[key] = self.coeffs.get(key, 0) - other.coeffs.get(key, 0)
            return Expression(coeffs=coeff)
        elif isinstance(other, (float, int)):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[None] = coeff.get(None, 0) - other
            return Expression(coeffs=coeff)

    def __rsub__(self, left: float | int) -> "Expression":
        return self.__sub__(left)

    def __neg__(self) -> "Expression":
        return 0 - self

    def __mul__(self, factor: float | int) -> "Expression":
        if not isinstance(factor, (float, int)):
            raise TypeError("Cannot multiply by non-numeric type")
        coeff = {key: factor*val for key, val in self.coeffs.items()}
        return Expression(coeffs=coeff)

    def __rmul__(self, factor: float | int) -> "Expression":
        return self.__mul__(factor)


class Solution(dict): ...


@dataclasses.dataclass(frozen=False)
class LPProblem:
    constraints_eqz: list[Expression] = dataclasses.field(default_factory=list)
    constraints_gez: list[Expression] = dataclasses.field(default_factory=list)
    linear_objective: Expression = dataclasses.field(
        default_factory=lambda: Expression({})
    )
    quadratic_objective: list[Expression] = dataclasses.field(default_factory=list)

    def add_gez(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.constraints_gez.append(expr)
        elif expr < 0:
            raise RuntimeError("No solution found")

    def add_lez(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.constraints_gez.append(-expr)
        elif expr > 0:
            raise RuntimeError("No solution found")

    def add_eqz(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.constraints_eqz.append(expr)
        elif expr != 0:
            raise RuntimeError("No solution found")

    def add_linear(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.linear_objective += expr
        else:
            print("LP Program Warning: no variables in linear objective term")

    def add_quadratic(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.quadratic_objective.append(expr)
        else:
            print("LP Program Warning: No variables in quadratic objective term")
    
    def add_abs(self, expr: Expression):
        """
        Use a slack variable to add an absolute value constraint.
        """
        slack = Variable()
        self.add_gez(slack - expr)
        self.add_gez(slack + expr)
        self.add_gez(1.0*slack)
        self.add_linear(1.0*slack)

    def __repr__(self):
        payload = "A Linear programming problem with {:} inequalies, {:} equalities, {:} quadratic".format(
            len(self.constraints_gez),
            len(self.constraints_eqz),
            len(self.quadratic_objective),
        )
        return payload

    @property
    def basis(self) -> list[Variable]:
        all_vars = Counter()
        for expr in self.constraints_eqz:
            all_vars.update(expr.coeffs.keys())
        for expr in self.constraints_gez:
            all_vars.update(expr.coeffs.keys())
        for expr in self.quadratic_objective:
            all_vars.update(expr.coeffs.keys())
        all_vars.update(self.linear_objective.coeffs.keys())
        all_vars.pop(None, None)  # The constant term is not a variable
        all_vars = list(all_vars.keys())
        return all_vars

    def __add__(self, other: "LPProblem") -> "LPProblem":
        if not isinstance(other, LPProblem):
            raise TypeError(f"Cannot add {type(other)} to LPProblem")
        return LPProblem(
            constraints_eqz=self.constraints_eqz + other.constraints_eqz,
            constraints_gez=self.constraints_gez + other.constraints_gez,
            linear_objective=self.linear_objective + other.linear_objective,
            quadratic_objective=self.quadratic_objective + other.quadratic_objective,
        )

    def solve(self) -> Solution:

        basis = self.basis
        if len(basis) == 0:
            return Solution()

        # Generate the sparse matrix for each value...
        # Inequality constraints
        A_gez_dat = []
        A_gez_i = []
        A_gez_j = []
        B_gez_dat = []
        for k in range(len(self.constraints_gez)):
            for key, val in self.constraints_gez[k].coeffs.items():
                if key is not None:
                    A_gez_dat.append(val)
                    A_gez_i.append(k)
                    A_gez_j.append(basis.index(key))
            B_gez_dat.append(self.constraints_gez[k].coeffs.get(None, 0))

        # Equality constraints
        A_eqz_dat = []
        A_eqz_i = []
        A_eqz_j = []
        B_eqz_dat = []
        for k in range(len(self.constraints_eqz)):
            for key, val in self.constraints_eqz[k].coeffs.items():
                if key is not None:
                    A_eqz_dat.append(val)
                    A_eqz_i.append(k)
                    A_eqz_j.append(basis.index(key))
            B_eqz_dat.append(self.constraints_eqz[k].get(None))

        # Linear objective
        C_dat = [self.linear_objective.coeffs.get(key, 0) for key in basis]

        # Quadratic objective
        Q_dat = []
        Q_i = []
        Q_j = []
        for k in range(len(self.quadratic_objective)):
            for key1, val1 in self.quadratic_objective[k].coeffs.items():
                for key2, val2 in self.quadratic_objective[k].coeffs.items():
                    if key1 is not None and key2 is not None:
                        Q_dat.append(val1 * val2)
                        Q_i.append(basis.index(key1))
                        Q_j.append(basis.index(key2))
                    elif key1 is None and key2 is not None:
                        C_dat[basis.index(key2)] += 0.5 * val1 * val2
                    elif key1 is not None and key2 is None:
                        C_dat[basis.index(key1)] += 0.5 * val1 * val2
                    elif key1 is None and key2 is None:
                        # This is the constant term and can be ignored
                        pass
                    else:
                        raise RuntimeError("I should never get here")

        A_gez_mat = scipy.sparse.coo_matrix(
            (A_gez_dat, (A_gez_i, A_gez_j)), shape=(len(B_gez_dat), len(basis))
        ).tocsc()
        B_gez_vec = np.array(B_gez_dat)

        A_eqz_mat = scipy.sparse.coo_matrix(
            (A_eqz_dat, (A_eqz_i, A_eqz_j)), shape=(len(B_eqz_dat), len(basis))
        ).tocsc()
        B_eqz_vec = np.array(B_eqz_dat)

        C_vec = np.array(C_dat)

        Q_mat = scipy.sparse.coo_matrix(
            (Q_dat, (Q_i, Q_j)), shape=(len(basis), len(basis))
        ).tocsc()

        # The quadratic problem uses slightly different variable symbols than
        # scipy, which is why the letters are all off...
        solution = solve_qp(
            P=Q_mat,
            q=C_vec,
            G=-A_gez_mat,
            h=B_gez_vec,
            A=A_eqz_mat,
            b=B_eqz_vec,
            solver="clarabel",
        )
        if solution is None:
            raise RuntimeError("No solution found")

        return Solution(zip(basis, solution))

 

def parallelizer(circuit:cirq.Circuit,
                 hyperparameters:dict[str, float] = {})-> cirq.Circuit:
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
    
    hyperparameters = {**{"linear": .01, "1q": 1.0, "2q": 1.0,"tags":0.5}, **hyperparameters}
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
    directed:nx.DiGraph = cirq.contrib.circuitdag.circuit_dag.CircuitDag.from_circuit(
        circuit2, can_reorder=reorder_check
    )
    directed2:nx.DiGraph = nx.transitive_reduction(directed)
    
    # ---
    # Turn into a linear program to solve
    # ---
    basis = {node:Variable() for node in directed2.nodes}
    lp = LPProblem()
    
    #All timesteps must be positive
    for node in directed2.nodes:
        lp.add_gez(1.0*basis[node])
    
    # Add ordering constraints
    for edge in directed2.edges:
        lp.add_gez(basis[edge[1]] - basis[edge[0]] - 1)
    
    # Add linear objective: minimize the total time
    lp.add_linear(hyperparameters["linear"]*sum(basis.values()))
    
    # Add ABS objective: similarity wants to go together.
    for node1 in directed2.nodes:
        for node2 in directed2.nodes:
            # Auto-similarity:
            U1 = cirq.unitary(node1.val)
            U2 = cirq.unitary(node2.val)
            similar = cirq.equal_up_to_global_phase(U1, U2,atol=1e-6)
            forced_order = nx.has_path(directed, node1, node2) or nx.has_path(directed, node2, node1)
            are_disjoint = len(set(node1.val.qubits).intersection(node2.val.qubits)) == 0
            if similar and not forced_order and are_disjoint:
                if len(node1.val.qubits)==1:
                    weight = hyperparameters["1q"]
                elif len(node1.val.qubits)==2:
                    weight = hyperparameters["2q"]
                else:
                    raise RuntimeError("Unsupported gate type")
                lp.add_abs((basis[node1] - basis[node2])*weight)
            
            # Topological (user) similarity:
            inter = set(node1.val.tags).intersection(set(node2.val.tags))
            if len(inter) > 0 and not forced_order and are_disjoint:
                weight = hyperparameters["tags"]*len(inter)
                lp.add_abs((basis[node1] - basis[node2])*weight)
    
    
    
    
    solution = lp.solve()
    solution2 = {gate:solution[basis[gate]] for gate in basis.keys()}     
    
    # Round to integer values
    for key,val in solution2.items():
        epoch = int(np.floor(val))
        solution2[key] = epoch
    
    # Convert to epochs
    unique_epochs = set(solution2.values())
    epochs = {epoch:[] for epoch in unique_epochs}
    for key,val in solution2.items():
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
        
        #twoq_gates2 = colorizer(twoq_gates)# Inlined.
        """
        Implements an edge coloring algorithm on a set of simultanious 2q gates,
        so that they can be done in an ordered manner so that no to gates use
        the same qubit in the same layer.
        """
        graph = nx.Graph()
        for gate in twoq_gates:
            if len(gate.qubits) != 2 and gate.gate != cirq.CZ:
                raise RuntimeError("Unsupported gate type")
            graph.add_edge(gate.qubits[0], gate.qubits[1])
        linegraph = nx.line_graph(graph)
        
        best = 1e99
        strategies = ['largest_first',
                    #'random_sequential',
                    'smallest_last',
                    'independent_set',
                    'connected_sequential_bfs',
                    'connected_sequential_dfs',
                    'saturation_largest_first']
        for strategy in strategies:
            colors = nx.algorithms.coloring.greedy_color(linegraph, strategy=strategy)
            if len(set(colors.values())) < best:
                best = len(set(colors.values()))
                best_colors = colors
        twoq_gates2 = [
            list(cirq.CZ(*k) for k, v in best_colors.items() if v == x) for x in set(best_colors.values())
        ]
        # -- end colorizer --
        
        
        
        # Extend the epochs.
        if len(oneq_gates) > 0:
            epochs_out.append(oneq_gates)
        epochs_out.extend(twoq_gates2)
                
    # Convert the epochs to a cirq circuit.
    moments = [cirq.Moment(epoch) for epoch in epochs_out]
    return cirq.Circuit(moments)


if __name__ == "__main__":
    qubits = cirq.LineQubit.range(8)
    circuit = cirq.Circuit(
        cirq.H(qubits[0]),
        cirq.CX(qubits[0], qubits[1]),
        cirq.CX(qubits[0], qubits[2]),
        cirq.CX(qubits[1], qubits[3]),
        cirq.CX(qubits[0], qubits[4]),
        cirq.CX(qubits[1], qubits[5]),
        cirq.CX(qubits[2], qubits[6]),
        cirq.CX(qubits[3], qubits[7]),
    )

    circuit2 = parallelizer(circuit)
    print(circuit2)
    print(len(circuit2.moments))

