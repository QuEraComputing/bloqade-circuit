from typing import Any, Set, Dict, Iterable, Optional, final
from itertools import chain
from collections import OrderedDict
from dataclasses import field, dataclass
from collections.abc import Sequence

from kirin import ir, graph, interp, idtable
from kirin.lattice import (
    SingletonMeta,
    BoundedLattice,
    SimpleJoinMixin,
    SimpleMeetMixin,
)
from kirin.analysis import Forward, ForwardFrame
from kirin.dialects import func

from bloqade.analysis import address
from bloqade.qasm2.parse.print import Printer
from bloqade.analysis.address.lattice import StaticContainer


@dataclass
class GateSchedule(
    SimpleJoinMixin["GateSchedule"],
    SimpleMeetMixin["GateSchedule"],
    BoundedLattice["GateSchedule"],
):
    """Abstract values for the scheduling interpreter."""

    @classmethod
    def bottom(cls) -> "GateSchedule":
        """Return the non-qubit lattice value."""
        return NotQubit()

    @classmethod
    def top(cls) -> "GateSchedule":
        """Return the lattice value that admits a qubit."""
        return Qubit()


@final
@dataclass
class NotQubit(GateSchedule, metaclass=SingletonMeta):
    """The bottom element of the scheduling lattice."""

    def is_subseteq(self, other: GateSchedule) -> bool:
        """Check the bottom element against another lattice value."""
        return True


@final
@dataclass
class Qubit(GateSchedule, metaclass=SingletonMeta):
    """The top element of the scheduling lattice."""

    def is_subseteq(self, other: GateSchedule) -> bool:
        """Check whether another lattice value also admits a qubit."""
        return isinstance(other, Qubit)


# Treat global gates as terminators for this analysis, e.g. split block in half.


@dataclass(slots=True)
class StmtDag(graph.Graph[ir.Statement]):
    """Track statement dependencies and the order statements were recorded."""

    id_table: idtable.IdTable[ir.Statement] = field(
        default_factory=lambda: idtable.IdTable()
    )
    stmts: Dict[str, ir.Statement] = field(default_factory=OrderedDict)
    out_edges: Dict[str, Set[str]] = field(default_factory=OrderedDict)
    inc_edges: Dict[str, Set[str]] = field(default_factory=OrderedDict)
    stmt_index: Dict[ir.Statement, int] = field(default_factory=OrderedDict)

    def update_index(self, node: ir.Statement):
        """Assign an index to a statement the first time it is seen."""
        if node not in self.stmt_index:
            self.stmt_index[node] = len(self.stmt_index)

    def add_node(self, node: ir.Statement):
        """Ensure a statement is in the graph and return its node ID."""
        node_id = self.id_table[node]
        self.stmts[node_id] = node
        self.update_index(node)
        self.out_edges.setdefault(node_id, set())
        self.inc_edges.setdefault(node_id, set())
        return node_id

    def add_edge(self, src: ir.Statement, dst: ir.Statement):
        """Record that the source must precede the destination."""
        src_id = self.add_node(src)
        dst_id = self.add_node(dst)

        self.out_edges[src_id].add(dst_id)
        self.inc_edges[dst_id].add(src_id)

    def get_parents(self, node: ir.Statement) -> Iterable[ir.Statement]:
        """Yield the direct predecessors of a statement."""
        return (
            self.stmts[node_id]
            for node_id in self.inc_edges.get(self.id_table[node], set())
        )

    def get_children(self, node: ir.Statement) -> Iterable[ir.Statement]:
        """Yield the direct successors of a statement."""
        return (
            self.stmts[node_id]
            for node_id in self.out_edges.get(self.id_table[node], set())
        )

    def get_neighbors(self, node: ir.Statement) -> Iterable[ir.Statement]:
        """Yield all statements directly connected to a statement."""
        return chain(self.get_parents(node), self.get_children(node))

    def get_nodes(self) -> Iterable[ir.Statement]:
        """Iterate over the statements in the graph."""
        return self.stmts.values()

    def get_edges(self) -> Iterable[tuple[ir.Statement, ir.Statement]]:
        """Yield the source and destination of each graph edge."""
        return (
            (self.stmts[src], self.stmts[dst])
            for src, dsts in self.out_edges.items()
            for dst in dsts
        )

    def print(
        self,
        printer: Optional["Printer"] = None,
        analysis: dict["ir.SSAValue", Any] | None = None,
    ) -> None:
        """Report that graph printing is unimplemented."""
        raise NotImplementedError

    def topological_groups(self):
        """Split the dag into topological groups where each group
        contains nodes that have no dependencies on each other, but
        have dependencies on nodes in one or more previous groups.

        Yields:
            List[str]: A list of node ids in a topological group


        Raises:
            ValueError: If a cyclic dependency is detected


        The idea is to yield all nodes with no dependencies, then remove
        those nodes from the graph repeating until no nodes are left
        or we reach some upper limit. Worse case is a linear dag,
        so we can use len(dag.stmts) as the upper limit

        If we reach the limit and there are still nodes left, then we
        have a cyclic dependency.
        """

        inc_edges = {k: set(v) for k, v in self.inc_edges.items()}

        check_next = inc_edges.keys()

        for _ in range(len(self.stmts)):
            if len(inc_edges) == 0:
                break

            group = [node_id for node_id in check_next if len(inc_edges[node_id]) == 0]
            yield group

            check_next = set()
            for n in group:
                inc_edges.pop(n)
                for m in self.out_edges[n]:
                    check_next.add(m)
                    inc_edges[m].remove(n)

        if inc_edges:
            raise ValueError("Cyclic dependency detected")


@dataclass
class DagScheduleAnalysis(Forward[GateSchedule]):
    """Build a dependency graph of qubit operations for each block."""

    keys = ["qasm2.schedule.dag"]
    lattice = GateSchedule

    address_analysis: Dict[ir.SSAValue, address.Address]
    use_def: Dict[int, ir.Statement] = field(init=False)
    last_unknown_access: ir.Statement | None = field(init=False)
    stmt_dag: StmtDag = field(init=False)
    stmt_dags: Dict[ir.Block, StmtDag] = field(init=False)

    def initialize(self):
        """Start a scheduling analysis with empty dependency state."""
        self.use_def = {}
        self.last_unknown_access = None
        self.stmt_dag = StmtDag()
        self.stmt_dags = {}
        return super().initialize()

    def push_current_dag(self, block: ir.Block):
        """Save the graph for a terminated block and reset block-local state."""
        assert block not in self.stmt_dags, "Block already in stmt_dags"

        for node in self.use_def.values():
            self.stmt_dag.add_node(node)

        self.stmt_dags[block] = self.stmt_dag
        self.stmt_dag = StmtDag()
        self.use_def = {}
        self.last_unknown_access = None

    def method_self(self, method: ir.Method) -> GateSchedule:
        """Represent the method itself as a non-qubit value."""
        return self.lattice.bottom()

    def eval_fallback(self, frame: ForwardFrame, node: ir.Statement):
        """Handle terminators and operations without a scheduling rule."""
        if node.has_trait(ir.IsTerminator):
            assert (
                node.parent_block is not None
            ), "Terminator statement has no parent block"
            self.push_current_dag(node.parent_block)
        elif not (node.has_trait(ir.Pure) or ir.MaybePure.is_pure(node)):
            # An unmodeled operation may access qubits, including in nested regions.
            self.stmt_dag.add_node(node)
            self._record_unknown_access(node)

        return tuple(self.lattice.top() for _ in node.results)

    def _add_dependency(self, previous: ir.Statement | None, stmt: ir.Statement):
        if previous is not None and previous is not stmt:
            self.stmt_dag.add_edge(previous, stmt)

    def _record_unknown_access(self, stmt: ir.Statement):
        """Order an operation that may access any qubit in the block."""
        self._add_dependency(self.last_unknown_access, stmt)
        for previous in set(self.use_def.values()):
            self._add_dependency(previous, stmt)
        self.use_def.clear()
        self.last_unknown_access = stmt

    def _update_dag(self, stmt: ir.Statement, addr: address.Address):
        if isinstance(addr, address.AddressQubit):
            self._add_dependency(self.last_unknown_access, stmt)
            self._add_dependency(self.use_def.get(addr.data), stmt)
            self.use_def[addr.data] = stmt
        elif isinstance(addr, address.AddressReg):
            for qubit in addr.qubits:
                self._update_dag(stmt, qubit)
        elif isinstance(addr, StaticContainer):
            for element in addr.data:
                self._update_dag(stmt, element)
        elif isinstance(
            addr,
            (address.UnknownQubit, address.UnknownReg, address.Unknown, address.Bottom),
        ):
            self._record_unknown_access(stmt)

    def update_dag(self, stmt: ir.Statement, args: Sequence[ir.SSAValue]):
        """Track a statement and the qubit dependencies of its operands."""
        self.stmt_dag.add_node(stmt)

        for arg in args:
            self._update_dag(
                stmt, self.address_analysis.get(arg, address.Address.bottom())
            )

    def get_dags(self, mt: ir.Method, args=None, kwargs=None):
        """Analyze a method and return the dependency graph for each block."""
        if args is None:
            args = tuple(self.lattice.top() for _ in mt.args)

        self.run(mt)
        return self.stmt_dags


@func.dialect.register(key="qasm2.schedule.dag")
class FuncImpl(interp.MethodTable):
    """Schedule function calls and account for possible captures."""

    @interp.impl(func.Invoke)
    @interp.impl(func.Call)
    def invoke(
        self,
        interp: DagScheduleAnalysis,
        frame: ForwardFrame,
        stmt: func.Invoke | func.Call,
    ):
        """Record call dependencies, including possible closure captures."""
        if isinstance(stmt, func.Call):
            return interp.eval_fallback(frame, stmt)
        interp.update_dag(stmt, stmt.inputs)
        return tuple(interp.lattice.top() for _ in stmt.results)
