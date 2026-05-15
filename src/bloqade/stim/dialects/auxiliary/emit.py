from kirin.interp import MethodTable, impl

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame

from . import stmts
from ._dialect import dialect


@dialect.register(key="emit.stim")
class EmitStimAuxMethods(MethodTable):

    def _format_with_tag(self, name: str, tag: str | None) -> str:
        """Format instruction name with optional tag annotation."""
        if tag:
            return f"{name}[{tag}]"
        return name

    @impl(stmts.ConstInt)
    def const_int(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.ConstInt):

        out: str = f"{stmt.value}"

        return (out,)

    @impl(stmts.ConstFloat)
    def const_float(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.ConstFloat
    ):

        out: str = f"{stmt.value:.8f}"

        return (out,)

    @impl(stmts.ConstBool)
    def const_bool(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.ConstBool
    ):
        out: str = "!" if stmt.value else ""

        return (out,)

    @impl(stmts.ConstStr)
    def const_str(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.ConstBool
    ):

        return (stmt.value,)

    @impl(stmts.Neg)
    def neg(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.Neg):

        operand: str = frame.get(stmt.operand)

        return ("-" + operand,)

    @impl(stmts.GetRecord)
    def get_rec(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.GetRecord):

        id: str = frame.get(stmt.id)
        out: str = f"rec[{id}]"

        return (out,)

    @impl(stmts.Tick)
    def tick(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.Tick):
        name = self._format_with_tag("TICK", stmt.tag)
        frame.write_line(name)

        return ()

    @impl(stmts.Detector)
    def detector(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.Detector):

        coords: tuple[str, ...] = frame.get_values(stmt.coord)
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        name = self._format_with_tag("DETECTOR", stmt.tag)

        coord_str: str = ", ".join(coords)
        target_str: str = " ".join(targets)
        if len(coords):
            frame.write_line(f"{name}({coord_str}) {target_str}")
        else:
            frame.write_line(f"{name} {target_str}")
        return ()

    @impl(stmts.ObservableInclude)
    def obs_include(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.ObservableInclude
    ):

        idx: str = frame.get(stmt.idx)
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        name = self._format_with_tag("OBSERVABLE_INCLUDE", stmt.tag)

        target_str: str = " ".join(targets)
        frame.write_line(f"{name}({idx}) {target_str}")

        return ()

    @impl(stmts.NewPauliString)
    def new_paulistr(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.NewPauliString
    ):

        string: tuple[str, ...] = frame.get_values(stmt.string)
        flipped: tuple[str, ...] = frame.get_values(stmt.flipped)
        targets: tuple[str, ...] = frame.get_values(stmt.targets)

        out = "*".join(
            f"{flp}{base}{tgt}" for flp, base, tgt in zip(flipped, string, targets)
        )

        return (out,)

    @impl(stmts.QubitCoordinates)
    def qubit_coordinates(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.QubitCoordinates
    ):

        coords: tuple[str, ...] = frame.get_values(stmt.coord)
        target: str = frame.get(stmt.target)
        name = self._format_with_tag("QUBIT_COORDS", stmt.tag)

        coord_str: str = ", ".join(coords)
        frame.write_line(f"{name}({coord_str}) {target}")

        return ()
