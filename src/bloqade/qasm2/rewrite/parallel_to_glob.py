from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import abc

from bloqade.analysis import address

from ..dialects import glob, parallel


@dataclass
class ParallelToGlobalRule(abc.RewriteRule):
    address_analysis: Dict[ir.SSAValue, address.Address]
    qubit_count: int

    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if not isinstance(node, parallel.UGate):
            return abc.RewriteResult()

        qargs = node.qargs
        qarg_addresses = self.address_analysis.get(qargs, None)

        if not isinstance(qarg_addresses, address.AddressReg):
            return abc.RewriteResult()

        theta, phi, lam = node.theta, node.phi, node.lam
        global_u = glob.UGate(qargs, theta=theta, phi=phi, lam=lam)
        node.replace_by(global_u)

        return abc.RewriteResult(has_done_something=True)
