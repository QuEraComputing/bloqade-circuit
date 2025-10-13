from typing import Tuple
from dataclasses import dataclass

from kirin.ir import SSAValue, Statement
from kirin.dialects import py, ilist
from kirin.rewrite.abc import RewriteRule, RewriteResult

from bloqade.squin import op, wire, noise as squin_noise, qubit
from bloqade.stim.dialects import noise as stim_noise
from bloqade.stim.rewrite.util import (
    get_const_value,
    create_wire_passthrough,
    insert_qubit_idx_after_apply,
)


@dataclass
class SquinNoiseToStim(RewriteRule):

    def rewrite_Statement(self, node: Statement) -> RewriteResult:
        match node:
            case qubit.Apply() | qubit.Broadcast() | wire.Apply() | wire.Broadcast():
                return self.rewrite_Apply_and_Broadcast(node)
            case _:
                return RewriteResult()

    def rewrite_Apply_and_Broadcast(
        self, stmt: qubit.Apply | qubit.Broadcast | wire.Apply | wire.Broadcast
    ) -> RewriteResult:
        """Rewrite Apply and Broadcast to their stim statements."""

        # this is an SSAValue, need it to be the actual operator
        applied_op = stmt.operator.owner

        if isinstance(applied_op, squin_noise.stmts.QubitLoss):
            return RewriteResult()

        if isinstance(applied_op, squin_noise.stmts.NoiseChannel):

            rewrite_method = getattr(self, f"rewrite_{type(applied_op).__name__}", None)
            # No rewrite method exists and the rewrite should stop
            if rewrite_method is None:
                return RewriteResult()

            qubit_idx_ssas = insert_qubit_idx_after_apply(stmt=stmt)
            if qubit_idx_ssas is None:
                return RewriteResult()

            stim_stmt = rewrite_method(stmt, qubit_idx_ssas)

            if isinstance(stmt, (wire.Apply, wire.Broadcast)):
                create_wire_passthrough(stmt)

            # guaranteed that you have a valid stim_stmt to plug in
            stmt.replace_by(stim_stmt)

            return RewriteResult(has_done_something=True)
        return RewriteResult()

    def rewrite_PauliError(
        self,
        stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.PauliError to XError, YError, ZError."""
        squin_channel = stmt.operator.owner
        assert isinstance(squin_channel, squin_noise.stmts.PauliError)
        basis = squin_channel.basis.owner
        assert isinstance(basis, op.stmts.PauliOp)
        p = get_const_value(float, squin_channel.p)

        p_stmt = py.Constant(p)
        p_stmt.insert_before(stmt)

        if isinstance(basis, op.stmts.X):
            stim_stmt = stim_noise.XError(targets=qubit_idx_ssas, p=p_stmt.result)
        elif isinstance(basis, op.stmts.Y):
            stim_stmt = stim_noise.YError(targets=qubit_idx_ssas, p=p_stmt.result)
        else:
            stim_stmt = stim_noise.ZError(targets=qubit_idx_ssas, p=p_stmt.result)
        return stim_stmt

    def rewrite_SingleQubitPauliChannel(
        self,
        stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.SingleQubitPauliChannel to stim.PauliChannel1."""

        squin_channel = stmt.operator.owner
        assert isinstance(squin_channel, squin_noise.stmts.SingleQubitPauliChannel)

        params = get_const_value(ilist.IList, squin_channel.params)
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

        params = get_const_value(ilist.IList, squin_channel.params)
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
        stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.Depolarize2 to stim.Depolarize2."""

        squin_channel = stmt.operator.owner
        assert isinstance(squin_channel, squin_noise.stmts.Depolarize2)

        p = get_const_value(float, squin_channel.p)
        p_stmt = py.Constant(p)
        p_stmt.insert_before(stmt)

        stim_stmt = stim_noise.Depolarize2(targets=qubit_idx_ssas, p=p_stmt.result)
        return stim_stmt

    def rewrite_Depolarize(
        self,
        stmt: qubit.Apply | qubit.Broadcast | wire.Broadcast | wire.Apply,
        qubit_idx_ssas: Tuple[SSAValue],
    ) -> Statement:
        """Rewrite squin.noise.Depolarize to stim.Depolarize1."""

        squin_channel = stmt.operator.owner
        assert isinstance(squin_channel, squin_noise.stmts.Depolarize)

        p = get_const_value(float, squin_channel.p)
        p_stmt = py.Constant(p)
        p_stmt.insert_before(stmt)

        stim_stmt = stim_noise.Depolarize1(targets=qubit_idx_ssas, p=p_stmt.result)
        return stim_stmt
