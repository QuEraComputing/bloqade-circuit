from typing import Dict, List, Tuple, cast
from dataclasses import field, dataclass

from kirin import ir
from kirin.rewrite import abc as rewrite_abc
from kirin.dialects import ilist

from bloqade.analysis import address
from bloqade.qasm2.dialects import uop, glob, noise, parallel


@dataclass
class NoiseRewriteRule(rewrite_abc.RewriteRule):
    """
    NOTE: This pass is not guaranteed to be supported long-term in bloqade. We will be
    moving towards a more general approach to noise modeling in the future.
    """

    address_analysis: Dict[ir.SSAValue, address.Address]
    qubit_ssa_value: Dict[int, ir.SSAValue]
    noise_model: noise.MoveNoiseModelABC = field(default_factory=noise.TwoRowZoneModel)

    def rewrite_Statement(self, node: ir.Statement) -> rewrite_abc.RewriteResult:
        if isinstance(node, uop.SingleQubitGate):
            return self.rewrite_single_qubit_gate(node)
        elif isinstance(node, uop.CZ):
            return self.rewrite_cz_gate(node)
        elif isinstance(node, (parallel.UGate, parallel.RZ)):
            return self.rewrite_parallel_single_qubit_gate(node)
        elif isinstance(node, parallel.CZ):
            return self.rewrite_parallel_cz_gate(node)
        elif isinstance(node, glob.UGate):
            return self.rewrite_global_single_qubit_gate(node)
        else:
            return rewrite_abc.RewriteResult()

    def insert_single_qubit_noise(
        self,
        node: ir.Statement,
        qargs: ir.SSAValue,
        probs: Tuple[float, float, float, float],
    ):
        noise.PauliChannel(qargs, px=probs[0], py=probs[1], pz=probs[2]).insert_before(
            node
        )
        noise.AtomLossChannel(qargs, prob=probs[3]).insert_before(node)

        return rewrite_abc.RewriteResult(has_done_something=True)

    def rewrite_single_qubit_gate(self, node: uop.SingleQubitGate):
        (qargs := ilist.New(values=(node.qarg,))).insert_before(node)
        return self.insert_single_qubit_noise(
            node, qargs.result, self.noise_model.local_errors
        )

    def rewrite_global_single_qubit_gate(self, node: glob.UGate):
        addrs = self.address_analysis[node.registers]
        if not isinstance(addrs, address.AddressTuple):
            return rewrite_abc.RewriteResult()

        qargs = []

        for addr in addrs.data:
            if not isinstance(addr, address.AddressReg):
                return rewrite_abc.RewriteResult()

            for qid in addr.data:
                qargs.append(self.qubit_ssa_value[qid])

        (qargs := ilist.New(values=tuple(qargs))).insert_before(node)
        return self.insert_single_qubit_noise(
            node, qargs.result, self.noise_model.global_errors
        )

    def rewrite_parallel_single_qubit_gate(self, node: parallel.RZ | parallel.UGate):
        addrs = self.address_analysis[node.qargs]
        if not isinstance(addrs, address.AddressTuple):
            return rewrite_abc.RewriteResult()

        if not all(isinstance(addr, address.AddressQubit) for addr in addrs.data):
            return rewrite_abc.RewriteResult()

        assert isinstance(node.qargs, ir.ResultValue)
        assert isinstance(node.qargs.stmt, ilist.New)
        return self.insert_single_qubit_noise(
            node, node.qargs, self.noise_model.local_errors
        )

    def move_noise_stmts(
        self,
        errors: Dict[Tuple[float, float, float, float], List[int]],
    ) -> list[ir.Statement]:

        nodes = []

        for probs, qubits in errors.items():
            if len(qubits) == 0:
                continue

            nodes.append(
                qargs := ilist.New(tuple(self.qubit_ssa_value[q] for q in qubits))
            )
            nodes.append(noise.AtomLossChannel(qargs.result, prob=probs[3]))
            nodes.append(
                noise.PauliChannel(qargs.result, px=probs[0], py=probs[1], pz=probs[2])
            )

        return nodes

    def cz_gate_noise(
        self,
        ctrls: ir.SSAValue,
        qargs: ir.SSAValue,
    ) -> list[ir.Statement]:
        return [
            noise.CZPauliChannel(
                ctrls,
                qargs,
                px_ctrl=self.noise_model.cz_paired_gate_px,
                py_ctrl=self.noise_model.cz_paired_gate_py,
                pz_ctrl=self.noise_model.cz_paired_gate_pz,
                px_qarg=self.noise_model.cz_paired_gate_px,
                py_qarg=self.noise_model.cz_paired_gate_py,
                pz_qarg=self.noise_model.cz_paired_gate_pz,
                paired=True,
            ),
            noise.CZPauliChannel(
                ctrls,
                qargs,
                px_ctrl=self.noise_model.cz_unpaired_gate_px,
                py_ctrl=self.noise_model.cz_unpaired_gate_py,
                pz_ctrl=self.noise_model.cz_unpaired_gate_pz,
                px_qarg=self.noise_model.cz_unpaired_gate_px,
                py_qarg=self.noise_model.cz_unpaired_gate_py,
                pz_qarg=self.noise_model.cz_unpaired_gate_pz,
                paired=False,
            ),
            noise.AtomLossChannel(ctrls, prob=self.noise_model.cz_gate_loss_prob),
            noise.AtomLossChannel(qargs, prob=self.noise_model.cz_gate_loss_prob),
        ]

    def rewrite_cz_gate(self, node: uop.CZ):

        has_done_something = False

        qarg_addr = self.address_analysis[node.qarg]
        ctrl_addr = self.address_analysis[node.ctrl]

        (ctrls := ilist.New([node.ctrl])).insert_before(node)
        (qargs := ilist.New([node.qarg])).insert_before(node)

        if isinstance(qarg_addr, address.AddressQubit) and isinstance(
            ctrl_addr, address.AddressQubit
        ):
            other_qubits = sorted(
                set(self.qubit_ssa_value.keys()) - {ctrl_addr.data, qarg_addr.data}
            )
            errors = self.noise_model.parallel_cz_errors(
                [ctrl_addr.data], [qarg_addr.data], other_qubits
            )

            move_noise_nodes = self.move_noise_stmts(errors)

            for new_node in move_noise_nodes:
                new_node.insert_before(node)
                has_done_something = True

        gate_noise_nodes = self.cz_gate_noise(ctrls.result, qargs.result)

        for new_node in gate_noise_nodes:
            new_node.insert_before(node)
            has_done_something = True

        return rewrite_abc.RewriteResult(has_done_something=has_done_something)

    def rewrite_parallel_cz_gate(self, node: parallel.CZ):
        ctrls = self.address_analysis[node.ctrls]
        qargs = self.address_analysis[node.qargs]

        has_done_something = False
        if (
            isinstance(ctrls, address.AddressTuple)
            and all(isinstance(addr, address.AddressQubit) for addr in ctrls.data)
            and isinstance(qargs, address.AddressTuple)
            and all(isinstance(addr, address.AddressQubit) for addr in qargs.data)
        ):
            ctrl_qubits = list(
                map(lambda addr: cast(address.AddressQubit, addr).data, ctrls.data)
            )
            qarg_qubits = list(
                map(lambda addr: cast(address.AddressQubit, addr).data, qargs.data)
            )
            rest = sorted(
                set(self.qubit_ssa_value.keys()) - set(ctrl_qubits + qarg_qubits)
            )
            errors = self.noise_model.parallel_cz_errors(ctrl_qubits, qarg_qubits, rest)
            move_noise_nodes = self.move_noise_stmts(errors)

            for new_node in move_noise_nodes:
                new_node.insert_before(node)
                has_done_something = True

        gate_noise_nodes = self.cz_gate_noise(node.ctrls, node.qargs)

        for new_node in gate_noise_nodes:
            new_node.insert_before(node)
            has_done_something = True

        return rewrite_abc.RewriteResult(has_done_something=has_done_something)
