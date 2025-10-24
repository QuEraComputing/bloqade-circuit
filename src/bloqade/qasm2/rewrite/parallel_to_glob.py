from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import abc
from kirin.dialects import ilist

from bloqade.analysis import address

from ..dialects import core, glob, parallel


@dataclass
class ParallelToGlobalRule(abc.RewriteRule):
    address_analysis: Dict[ir.SSAValue, address.Address]

    def rewrite_Statement(self, node: ir.Statement) -> abc.RewriteResult:
        if not isinstance(node, parallel.UGate):
            return abc.RewriteResult()

        qargs = node.qargs
        qargs_address = self.address_analysis.get(qargs, address.Unknown())

        if not isinstance(qargs_address, address.AddressReg):
            return abc.RewriteResult()

        qregs = self._get_all_qreg(qargs.owner)

        if len(qregs) != 1:
            return abc.RewriteResult()

        qreg = next(iter(qregs))

        qreg_address = self.address_analysis.get(qreg, address.Unknown())

        if not isinstance(qreg_address, address.AddressReg):
            return abc.RewriteResult()

        if set(qargs_address.data) != set(qreg_address.data):
            return abc.RewriteResult()

        return self._rewrite_parallel_to_glob(node)

    @staticmethod
    def _rewrite_parallel_to_glob(node: parallel.UGate) -> abc.RewriteResult:
        theta, phi, lam = node.theta, node.phi, node.lam
        global_u = glob.UGate(node.qargs, theta=theta, phi=phi, lam=lam)
        node.replace_by(global_u)
        return abc.RewriteResult(has_done_something=True)

    @staticmethod
    def _get_all_qreg(owner: ir.Statement | ir.Block):
        stack = [owner]
        qregs: set[ir.SSAValue] = set()
        while stack:
            current = stack.pop()

            if isinstance(current, core.stmts.QRegGet):
                stack.append(current.reg.owner)
            elif isinstance(current, ilist.New):
                for val in current.values:
                    stack.append(val.owner)

            elif isinstance(current, core.QRegNew):
                qregs.add(current.result)

        return qregs

    @staticmethod
    def _find_qreg(
        qargs_owner: ir.Statement | ir.Block, idxs: set
    ) -> tuple[set, core.stmts.QRegNew | None]:

        if isinstance(qargs_owner, core.stmts.QRegGet):
            idxs.add(qargs_owner.idx)
            qreg = qargs_owner.reg.owner
            if not isinstance(qreg, core.stmts.QRegNew):
                # NOTE: this could potentially be casted
                qreg = None
            return idxs, qreg

        if isinstance(qargs_owner, ilist.New):
            vals = qargs_owner.values
            if len(vals) == 0:
                return idxs, None

            idxs, first_qreg = ParallelToGlobalRule._find_qreg(vals[0].owner, idxs)
            for val in vals[1:]:
                idxs, qreg = ParallelToGlobalRule._find_qreg(val.owner, idxs)
                if qreg != first_qreg:
                    return idxs, None

            return idxs, first_qreg

        return idxs, None
