from typing import Dict
from dataclasses import dataclass

from kirin import ir
from kirin.rewrite import abc
from kirin.analysis import const
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
        qarg_addresses = self.address_analysis.get(qargs, None)

        if isinstance(qarg_addresses, address.AddressReg):
            # NOTE: we only have an AddressReg if it's an entire register, definitely rewrite that
            return self._rewrite_parallel_to_glob(node)

        if not isinstance(qarg_addresses, address.AddressTuple):
            return abc.RewriteResult()

        idxs, qreg = self._find_qreg(qargs.owner, set())

        if qreg is None:
            # NOTE: no unique register found
            return abc.RewriteResult()

        if not isinstance(hint := qreg.n_qubits.hints.get("const"), const.Value):
            # NOTE: non-constant number of qubits
            return abc.RewriteResult()

        n = hint.data
        if len(idxs) != n:
            # NOTE: not all qubits of the register are there
            return abc.RewriteResult()

        return self._rewrite_parallel_to_glob(node)

    @staticmethod
    def _rewrite_parallel_to_glob(node: parallel.UGate) -> abc.RewriteResult:
        theta, phi, lam = node.theta, node.phi, node.lam
        global_u = glob.UGate(node.qargs, theta=theta, phi=phi, lam=lam)
        node.replace_by(global_u)
        return abc.RewriteResult(has_done_something=True)

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
