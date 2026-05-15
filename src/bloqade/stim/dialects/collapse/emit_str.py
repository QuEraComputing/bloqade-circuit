from kirin.interp import MethodTable, impl

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame

from . import stmts
from ._dialect import dialect
from .stmts.reset import Reset
from .stmts.measure import Measurement


@dialect.register(key="emit.stim")
class EmitStimCollapseMethods(MethodTable):

    def _format_with_tag(self, name: str, tag: str | None) -> str:
        """Format instruction name with optional tag annotation."""
        if tag:
            return f"{name}[{tag}]"
        return name

    meas_map: dict[str, str] = {
        stmts.MX.name: "MX",
        stmts.MY.name: "MY",
        stmts.MZ.name: "MZ",
        stmts.MXX.name: "MXX",
        stmts.MYY.name: "MYY",
        stmts.MZZ.name: "MZZ",
    }

    @impl(stmts.MX)
    @impl(stmts.MY)
    @impl(stmts.MZ)
    @impl(stmts.MXX)
    @impl(stmts.MYY)
    @impl(stmts.MZZ)
    def get_measure(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: Measurement):

        probability: str = frame.get(stmt.p)
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        name = self._format_with_tag(self.meas_map[stmt.name], stmt.tag)

        out = f"{name}({probability}) " + " ".join(targets)
        frame.write_line(out)

        return ()

    reset_map: dict[str, str] = {
        stmts.RX.name: "RX",
        stmts.RY.name: "RY",
        stmts.RZ.name: "RZ",
    }

    @impl(stmts.RX)
    @impl(stmts.RY)
    @impl(stmts.RZ)
    def get_reset(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: Reset):

        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        name = self._format_with_tag(self.reset_map[stmt.name], stmt.tag)

        out = f"{name} " + " ".join(targets)
        frame.write_line(out)

        return ()

    @impl(stmts.PPMeasurement)
    def pp_measure(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.PPMeasurement
    ):
        probability: str = frame.get(stmt.p)
        targets: tuple[str, ...] = tuple(
            targ.upper() for targ in frame.get_values(stmt.targets)
        )
        name = self._format_with_tag("MPP", stmt.tag)

        out = f"{name}({probability}) " + " ".join(targets)
        frame.write_line(out)

        return ()
