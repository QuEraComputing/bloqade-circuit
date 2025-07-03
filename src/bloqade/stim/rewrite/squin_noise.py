from typing import Dict, Tuple
from dataclasses import dataclass

from kirin.ir import SSAValue, Statement
from kirin.analysis import const
from kirin.dialects import py
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import wire, noise as squin_noise, qubit
from bloqade.stim.dialects import noise as stim_noise
from bloqade.stim.rewrite.util import (
    create_wire_passthrough,
    insert_qubit_idx_after_apply,
)


@dataclass
class SquinNoiseToStim(RewriteRule):

    cp_results: Dict[SSAValue, const.Result]

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        match node:
            case qubit.Apply() | qubit.Broadcast():
                return self.rewrite_Apply_and_Broadcast(node)
            case _:
                return RewriteResult()

    def rewrite_Apply_and_Broadcast(
        self, stmt: qubit.Apply | qubit.Broadcast
    ) -> RewriteResult:
        """Rewrite Apply and Broadcast to their stim statements."""

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner

        if isinstance(applied_op, squin_noise.stmts.NoiseChannel):

            qubit_idx_ssas = insert_qubit_idx_after_apply(stmt=stmt)
            if qubit_idx_ssas is None:
                return RewriteResult()

            stim_stmt = None
            if isinstance(applied_op, squin_noise.stmts.SingleQubitPauliChannel):
                stim_stmt = self.rewrite_SingleQubitPauliChannel(stmt, qubit_idx_ssas)
            elif isinstance(applied_op, squin_noise.stmts.TwoQubitPauliChannel):
                stim_stmt = self.rewrite_TwoQubitPauliChannel(stmt, qubit_idx_ssas)

            if isinstance(stmt, (wire.Apply, wire.Broadcast)):
                create_wire_passthrough(stmt)

            if stim_stmt is not None:
                stmt.replace_by(stim_stmt)
            if len(stmt.operator.owner.result.uses) == 0:
                stmt.operator.owner.delete()

            return RewriteResult(has_done_something=True)
        return RewriteResult()

    def rewrite_SingleQubitPauliChannel(
        self,
        stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.SingleQubitPauliChannel to stim.PauliChannel1."""

        squin_channel = stmt.operator.owner
        assert isinstance(squin_channel, squin_noise.stmts.SingleQubitPauliChannel)

        params = self.cp_results.get(squin_channel.params).data
        new_stmts = [
            p_x := py.Constant(params[0]),
            p_y := py.Constant(params[1]),
            p_z := py.Constant(params[2]),
        ]
        for new_stmt in new_stmts:
            new_stmt.insert_before(stmt)

        stim_stmt = stim_noise.PauliChannel1(
            targets=qubit_idx_ssas,
            px=p_x.result,
            py=p_y.result,
            pz=p_z.result,
        )
        return stim_stmt

    def rewrite_TwoQubitPauliChannel(
        self,
        stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.SingleQubitPauliChannel to stim.PauliChannel1."""

        squin_channel = stmt.operator.owner
        assert isinstance(squin_channel, squin_noise.stmts.TwoQubitPauliChannel)

        params = self.cp_results.get(squin_channel.params).data
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
