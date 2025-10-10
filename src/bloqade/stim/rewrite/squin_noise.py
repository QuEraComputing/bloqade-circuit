import itertools
from typing import Tuple
from dataclasses import dataclass

from kirin.ir import SSAValue, Statement
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import noise as squin_noise
from bloqade.stim.dialects import noise as stim_noise
from bloqade.stim.rewrite.util import get_const_value, insert_qubit_idx_from_address


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

        px_float = get_const_value(float, stmt.px)
        py_float = get_const_value(float, stmt.py)
        pz_float = get_const_value(float, stmt.pz)

        p_x = py.Constant(px_float)
        p_x.insert_before(stmt)
        p_y = py.Constant(py_float)
        p_y.insert_before(stmt)
        p_z = py.Constant(pz_float)
        p_z.insert_before(stmt)

        stim_stmt = stim_noise.PauliChannel1(
            targets=qubit_idx_ssas,
            px=p_x.result,
            py=p_y.result,
            pz=p_z.result,
        )
        return stim_stmt

    def rewrite_QubitLoss(
        self,
        stmt: squin_noise.stmts.QubitLoss,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.QubitLoss to stim.TrivialError."""
        p = get_const_value(float, stmt.p)
        p_stmt = py.Constant(p)
        p_stmt.insert_before(stmt)

        stim_stmt = stim_noise.QubitLoss(
            targets=qubit_idx_ssas,
            probs=(p_stmt.result,),
        )

        return stim_stmt

    def rewrite_Depolarize(
        self,
        stmt: squin_noise.stmts.Depolarize,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.Depolarize to stim.Depolarize1."""
        p = get_const_value(float, stmt.p)
        p_stmt = py.Constant(p)
        p_stmt.insert_before(stmt)

        stim_stmt = stim_noise.Depolarize1(
            targets=qubit_idx_ssas,
            p=p_stmt.result,
        )

        return stim_stmt

    def rewrite_TwoQubitPauliChannel(
        self,
        stmt: squin_noise.stmts.TwoQubitPauliChannel,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.TwoQubitPauliChannel to stim.PauliChannel2."""

        params = get_const_value(ilist.IList, stmt.probabilities)
        param_stmts = [py.Constant(p) for p in params]
        for param_stmt in param_stmts:
            param_stmt.insert_before(stmt)

        stim_stmt = stim_noise.PauliChannel2(
            targets=qubit_idx_ssas,
            pix=param_stmts[0].result,
            piy=param_stmts[1].result,
            piz=param_stmts[2].result,
            pxi=param_stmts[3].result,
            pxx=param_stmts[4].result,
            pxy=param_stmts[5].result,
            pxz=param_stmts[6].result,
            pyi=param_stmts[7].result,
            pyx=param_stmts[8].result,
            pyy=param_stmts[9].result,
            pyz=param_stmts[10].result,
            pzi=param_stmts[11].result,
            pzx=param_stmts[12].result,
            pzy=param_stmts[13].result,
            pzz=param_stmts[14].result,
        )
        return stim_stmt

    def rewrite_Depolarize2(
        self,
        stmt: squin_noise.stmts.Depolarize2,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.Depolarize2 to stim.Depolarize2."""

        p = get_const_value(float, stmt.p)
        p_stmt = py.Constant(p)
        p_stmt.insert_before(stmt)

        stim_stmt = stim_noise.Depolarize2(targets=qubit_idx_ssas, p=p_stmt.result)
        return stim_stmt
