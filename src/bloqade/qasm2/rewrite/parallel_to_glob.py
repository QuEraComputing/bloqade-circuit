from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import abc

from bloqade.analysis import address

from ..dialects import glob, parallel


@dataclass
class ParallelToGlobalRule(abc.RewriteRule):
    address_analysis: Dict[ir.SSAValue, address.Address]

    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if not isinstance(node, parallel.UGate):
            return abc.RewriteResult()

        qargs = node.qargs
        qarg_addresses = self.address_analysis.get(qargs, None)

        if not isinstance(qarg_addresses, address.AddressReg | address.AddressTuple):
            return abc.RewriteResult()

        needs_rewrite = isinstance(qarg_addresses, address.AddressReg)
        if not needs_rewrite:
            # NOTE: if we're looking at a tuple, need to check and see if all qubits are from the same register
            registers = [
                val
                for val in self.address_analysis.values()
                if isinstance(val, address.AddressReg)
            ]

            qarg_addr_set: set[int] = set()
            for addr in qarg_addresses.data:
                if not isinstance(addr, address.AddressQubit):
                    # NOTE: somehow not a qubit in the list, let's bail
                    return abc.RewriteResult()

                qarg_addr_set.add(addr.data)

            for reg in registers:
                needs_rewrite = set(reg.data) == qarg_addr_set
                if needs_rewrite:
                    break

        if not needs_rewrite:
            return abc.RewriteResult()

        theta, phi, lam = node.theta, node.phi, node.lam
        global_u = glob.UGate(qargs, theta=theta, phi=phi, lam=lam)
        node.replace_by(global_u)

        return abc.RewriteResult(has_done_something=True)
