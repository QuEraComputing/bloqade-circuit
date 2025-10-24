import itertools
from typing import Tuple
from dataclasses import dataclass

from kirin import types
from kirin.ir import SSAValue, Statement
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import noise as squin_noise
from bloqade.stim.dialects import noise as stim_noise
from bloqade.stim.rewrite.util import insert_qubit_idx_from_address
from bloqade.analysis.address.lattice import AddressReg, PartialIList
from bloqade.squin.rewrite.wrap_analysis import AddressAttribute


@dataclass
class SquinNoiseToStim(RewriteRule):

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        match node:
            case squin_noise.stmts.NoiseChannel():
                return self.rewrite_NoiseChannel(node)
            case _:
                return RewriteResult()

    def rewrite_NoiseChannel(
        self, stmt: squin_noise.stmts.NoiseChannel
    ) -> RewriteResult:
        """Rewrite NoiseChannel statements to their stim equivalents."""

        rewrite_method = getattr(self, f"rewrite_{type(stmt).__name__}", None)

        # No rewrite method exists and the rewrite should stop
        if rewrite_method is None:
            return RewriteResult()
        if isinstance(stmt, squin_noise.stmts.CorrelatedQubitLoss):
            # CorrelatedQubitLoss represents a broadcast operation, but Stim does not
            # support broadcasting for multi-qubit noise channels.
            # Therefore, we must expand the broadcast into individual stim statements.
            qubit_address_attr = stmt.qubits.hints.get("address", None)

            if not isinstance(qubit_address_attr, AddressAttribute):
                return RewriteResult()

            if not isinstance(address := qubit_address_attr.address, PartialIList):
                return RewriteResult()

            if not types.is_tuple_of(data := address.data, AddressReg):
                return RewriteResult()

            for address_reg in data:

                qubit_idx_ssas = insert_qubit_idx_from_address(
                    AddressAttribute(address_reg), stmt
                )

                stim_stmt = rewrite_method(stmt, qubit_idx_ssas)
                stim_stmt.insert_before(stmt)

            stmt.delete()

            return RewriteResult(has_done_something=True)

        if isinstance(stmt, squin_noise.stmts.SingleQubitNoiseChannel):
            qubit_address_attr = stmt.qubits.hints.get("address", None)
            if qubit_address_attr is None:
                return RewriteResult()
            qubit_idx_ssas = insert_qubit_idx_from_address(qubit_address_attr, stmt)

        elif isinstance(stmt, squin_noise.stmts.TwoQubitNoiseChannel):
            control_address_attr = stmt.controls.hints.get("address", None)
            target_address_attr = stmt.targets.hints.get("address", None)
            if control_address_attr is None or target_address_attr is None:
                return RewriteResult()
            control_qubit_idx_ssas = insert_qubit_idx_from_address(
                control_address_attr, stmt
            )
            target_qubit_idx_ssas = insert_qubit_idx_from_address(
                target_address_attr, stmt
            )
            if control_qubit_idx_ssas is None or target_qubit_idx_ssas is None:
                return RewriteResult()

            # For stim statements you want to interleave the control and target qubit indices:
            # ex: CX controls = (0,1) targets = (2,3) in stim is: CX 0 2 1 3
            qubit_idx_ssas = list(
                itertools.chain.from_iterable(
                    zip(control_qubit_idx_ssas, target_qubit_idx_ssas)
                )
            )
        else:
            return RewriteResult()

        # guaranteed that you have a valid stim_stmt to plug in
        stim_stmt = rewrite_method(stmt, tuple(qubit_idx_ssas))
        stmt.replace_by(stim_stmt)

        return RewriteResult(has_done_something=True)

    def rewrite_SingleQubitPauliChannel(
        self,
        stmt: squin_noise.stmts.SingleQubitPauliChannel,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.SingleQubitPauliChannel to stim.PauliChannel1."""

        stim_stmt = stim_noise.PauliChannel1(
            targets=qubit_idx_ssas,
            px=stmt.px,
            py=stmt.py,
            pz=stmt.pz,
        )
        return stim_stmt

    def rewrite_QubitLoss(
        self,
        stmt: squin_noise.stmts.QubitLoss,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.QubitLoss to stim.TrivialError."""

        stim_stmt = stim_noise.QubitLoss(
            targets=qubit_idx_ssas,
            probs=(stmt.p,),
        )

        return stim_stmt

    def rewrite_CorrelatedQubitLoss(
        self,
        stmt: squin_noise.stmts.CorrelatedQubitLoss,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.CorrelatedQubitLoss to stim.CorrelatedQubitLoss."""
        stim_stmt = stim_noise.CorrelatedQubitLoss(
            targets=qubit_idx_ssas,
            probs=(stmt.p,),
        )

        return stim_stmt

    def rewrite_Depolarize(
        self,
        stmt: squin_noise.stmts.Depolarize,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.Depolarize to stim.Depolarize1."""

        stim_stmt = stim_noise.Depolarize1(
            targets=qubit_idx_ssas,
            p=stmt.p,
        )

        return stim_stmt

    def rewrite_TwoQubitPauliChannel(
        self,
        stmt: squin_noise.stmts.TwoQubitPauliChannel,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.TwoQubitPauliChannel to stim.PauliChannel2."""

        params = stmt.probabilities
        prob_ssas = []
        for idx in range(15):
            idx_stmt = py.Constant(value=idx)
            idx_stmt.insert_before(stmt)
            getitem_stmt = py.GetItem(obj=params, index=idx_stmt.result)
            getitem_stmt.insert_before(stmt)
            prob_ssas.append(getitem_stmt.result)

        stim_stmt = stim_noise.PauliChannel2(
            targets=qubit_idx_ssas,
            pix=prob_ssas[0],
            piy=prob_ssas[1],
            piz=prob_ssas[2],
            pxi=prob_ssas[3],
            pxx=prob_ssas[4],
            pxy=prob_ssas[5],
            pxz=prob_ssas[6],
            pyi=prob_ssas[7],
            pyx=prob_ssas[8],
            pyy=prob_ssas[9],
            pyz=prob_ssas[10],
            pzi=prob_ssas[11],
            pzx=prob_ssas[12],
            pzy=prob_ssas[13],
            pzz=prob_ssas[14],
        )
        return stim_stmt

    def rewrite_Depolarize2(
        self,
        stmt: squin_noise.stmts.Depolarize2,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.Depolarize2 to stim.Depolarize2."""

        stim_stmt = stim_noise.Depolarize2(targets=qubit_idx_ssas, p=stmt.p)
        return stim_stmt
