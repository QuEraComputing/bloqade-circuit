from typing import Callable
from dataclasses import field, dataclass

from kirin import ir
from kirin.lattice import EmptyLattice
from kirin.analysis import Forward

from bloqade.analysis.address import AddressQubit
from bloqade.squin.analysis.nsites import Sites

from ..address import Address

AlgorithmCallable = Callable[
    [list[tuple[tuple[int, int], ...]], int, tuple[int, int]],
    dict[int, tuple[int, int]],
]


@dataclass
class LayoutAnalysis(Forward):
    keys = ["circuit.layout"]
    lattice = EmptyLattice

    addr_analysis: dict[ir.SSAValue, Address]
    nsite_analysis: dict[ir.SSAValue, Sites]

    stages: list[tuple[tuple[int, int], ...]] = field(init=False, default_factory=list)

    def initialize(self):
        self.stages.clear()
        return super().initialize()

    def run_method(self, method: ir.Method, args: tuple[EmptyLattice, ...]):
        return self.run_callable(method.code, (self.lattice.bottom(),) + args)

    def eval_stmt_fallback(self, frame, stmt):
        return (self.lattice.bottom(),)

    def get_layout(
        self,
        method,
        dimension: tuple[int, int],
        num_qubits: int,
        algorithm: AlgorithmCallable,
    ):

        self.run_analysis(method)
        raw_layout = algorithm(self.stages, num_qubits, dimension)
        return {AddressQubit(qid): val for qid, val in raw_layout}

    # def run_analysis(self, method: ir.Method):
    # addr_analysis = AddressAnalysis(self.dialects)
    # self.addr_analysis, _ = addr_analysis.run_analysis(method)
    # wr_dict = {}
    # w_dict = {}
    # stmts = []

    # for e in self.addr_analysis.entries:
    #     if e.type == squin.wire.WireType:
    #         if e.owner not in stmts:
    #             stmts.append(e.owner)

    #         if isinstance(e.stmt, squin.wire.Unwrap):
    #             w_dict[e.owner] = [self.addr_analysis.entries[e].origin_qubit.data]
    #             wr_dict[e] = self.addr_analysis.entries[e].origin_qubit.data

    #         elif isinstance(e.stmt, squin.wire.Broadcast):

    #             if e.owner not in w_dict:
    #                 idx = 1
    #                 w_dict[e.owner] = []
    #             wr_dict[e] = wr_dict[e.owner.args.field[idx]]
    #             w_dict[e.owner].append(wr_dict[e])
    #             idx += 1
    #     else:
    #         if e.name != "main_self":
    #             if isinstance(e.stmt, squin.qubit.New):
    #                 N = e.stmt.args[0].stmt.args.node.value.data

    # print(stmts)
    # print(w_dict)

    # cz_blocks, _ = stmt_to_cz_blocks(stmts, w_dict)
    # if choice == 'sabre':
    #     self.initial_layout = sabre_initial_layout(self.stages, N, dim)
    # elif choice == 'enola':
    #     self.initial_layout = enola_initial_layout(cz_blocks, N, dim)
