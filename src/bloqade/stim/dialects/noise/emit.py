from kirin.interp import MethodTable, impl

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.stim")
class EmitStimNoiseMethods(MethodTable):

    single_p_error_map: dict[str, str] = {
        stmts.Depolarize1.name: "DEPOLARIZE1",
        stmts.Depolarize2.name: "DEPOLARIZE2",
        stmts.XError.name: "X_ERROR",
        stmts.YError.name: "Y_ERROR",
        stmts.ZError.name: "Z_ERROR",
    }

    def _format_with_tag(self, name: str, tag: str | None) -> str:
        """Format instruction name with optional tag annotation."""
        if tag:
            return f"{name}[{tag}]"
        return name

    @impl(stmts.XError)
    @impl(stmts.YError)
    @impl(stmts.ZError)
    @impl(stmts.Depolarize1)
    @impl(stmts.Depolarize2)
    def single_p_error(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.Depolarize1
    ):

        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        p: str = frame.get(stmt.p)
        name = self._format_with_tag(self.single_p_error_map[stmt.name], stmt.tag)
        res = f"{name}({p}) " + " ".join(targets)
        frame.write_line(res)

        return ()

    @impl(stmts.PauliChannel1)
    def pauli_channel1(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.PauliChannel1
    ):

        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        px: str = frame.get(stmt.px)
        py: str = frame.get(stmt.py)
        pz: str = frame.get(stmt.pz)
        name = self._format_with_tag("PAULI_CHANNEL_1", stmt.tag)
        res = f"{name}({px}, {py}, {pz}) " + " ".join(targets)
        frame.write_line(res)

        return ()

    @impl(stmts.PauliChannel2)
    def pauli_channel2(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.PauliChannel2
    ):

        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        prob: tuple[str, ...] = frame.get_values(stmt.args)[
            :15
        ]  # extract the first 15 argument, which is the probabilities
        prob_str: str = ", ".join(prob)
        name = self._format_with_tag("PAULI_CHANNEL_2", stmt.tag)

        res = f"{name}({prob_str}) " + " ".join(targets)
        frame.write_line(res)

        return ()

    @impl(stmts.TrivialError)
    @impl(stmts.QubitLoss)
    def non_stim_error(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.TrivialError
    ):

        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        prob: tuple[str, ...] = frame.get_values(stmt.probs)
        prob_str: str = ", ".join(prob)
        name = self._format_with_tag(f"I_ERROR[{stmt.name}]", stmt.tag)

        res = f"{name}({prob_str}) " + " ".join(targets)
        frame.write_line(res)

        return ()

    @impl(stmts.TrivialCorrelatedError)
    @impl(stmts.CorrelatedQubitLoss)
    def non_stim_corr_error(
        self,
        emit: EmitStimMain,
        frame: EmitStimFrame,
        stmt: stmts.TrivialCorrelatedError,
    ):

        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        prob: tuple[str, ...] = frame.get_values(stmt.probs)
        prob_str: str = ", ".join(prob)
        name = self._format_with_tag(
            f"I_ERROR[{stmt.name}:{emit.correlated_error_count}]", stmt.tag
        )

        res = f"{name}({prob_str}) " + " ".join(targets)
        emit.correlated_error_count += 1
        frame.write_line(res)

        return ()
