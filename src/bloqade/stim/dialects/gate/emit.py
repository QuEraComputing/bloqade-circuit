from kirin.interp import MethodTable, impl

from bloqade.stim.emit.stim_str import EmitStimMain, EmitStimFrame

from . import stmts
from ._dialect import dialect
from .stmts.base import SingleQubitGate, ControlledTwoQubitGate


@dialect.register(key="emit.stim")
class EmitStimGateMethods(MethodTable):

    gate_1q_map: dict[str, tuple[str, str]] = {
        stmts.Identity.name: ("I", "I"),
        stmts.X.name: ("X", "X"),
        stmts.Y.name: ("Y", "Y"),
        stmts.Z.name: ("Z", "Z"),
        stmts.H.name: ("H", "H"),
        stmts.S.name: ("S", "S_DAG"),
        stmts.SqrtX.name: ("SQRT_X", "SQRT_X_DAG"),
        stmts.SqrtY.name: ("SQRT_Y", "SQRT_Y_DAG"),
        stmts.SqrtZ.name: ("SQRT_Z", "SQRT_Z_DAG"),
    }

    @impl(stmts.Identity)
    @impl(stmts.X)
    @impl(stmts.Y)
    @impl(stmts.Z)
    @impl(stmts.S)
    @impl(stmts.H)
    @impl(stmts.SqrtX)
    @impl(stmts.SqrtY)
    @impl(stmts.SqrtZ)
    def single_qubit_gate(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: SingleQubitGate
    ):
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        res = f"{self.gate_1q_map[stmt.name][int(stmt.dagger)]} " + " ".join(targets)
        frame.write_line(res)

        return ()

    @impl(stmts.T)
    def t_gate(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.T):
        """Emit T gate as S[T] or S_DAG[T] in Stim annotation format."""
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        gate_name = "S_DAG" if stmt.dagger else "S"
        res = f"{gate_name}[T] " + " ".join(targets)
        frame.write_line(res)
        return ()

    def _format_angle(self, angle_str: str) -> str:
        """Format angle value as a multiple of pi."""
        angle_turns = float(angle_str)
        pi_multiple = angle_turns * 2.0
        return f"{pi_multiple}*pi"

    @impl(stmts.Rx)
    @impl(stmts.Ry)
    @impl(stmts.Rz)
    def rotation_gate(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.Rx):
        """Emit rotation gate as I[R_X/R_Y/R_Z(theta=...)] in Stim annotation format."""
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        angle_str: str = self._format_angle(frame.get(stmt.angle))
        res = f"I[{stmt.name}(theta={angle_str})] " + " ".join(targets)
        frame.write_line(res)
        return ()

    @impl(stmts.U3)
    def u3_gate(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.U3):
        """Emit U3 gate as I[U3(theta=..., phi=..., lambda=...)] in Stim annotation format."""
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        theta_str: str = self._format_angle(frame.get(stmt.theta))
        phi_str: str = self._format_angle(frame.get(stmt.phi))
        lam_str: str = self._format_angle(frame.get(stmt.lam))
        res = f"I[U3(theta={theta_str}, phi={phi_str}, lambda={lam_str})] " + " ".join(
            targets
        )
        frame.write_line(res)
        return ()

    gate_2q_map: dict[str, tuple[str, str]] = {
        stmts.Swap.name: ("SWAP", "SWAP"),
    }

    @impl(stmts.Swap)
    def two_qubit_gate(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: ControlledTwoQubitGate
    ):
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        res = f"{self.gate_ctrl_2q_map[stmt.name][int(stmt.dagger)]} " + " ".join(
            targets
        )
        frame.write_line(res)

        return ()

    gate_ctrl_2q_map: dict[str, tuple[str, str]] = {
        stmts.CX.name: ("CX", "CX"),
        stmts.CY.name: ("CY", "CY"),
        stmts.CZ.name: ("CZ", "CZ"),
        stmts.Swap.name: ("SWAP", "SWAP"),
    }

    @impl(stmts.CX)
    @impl(stmts.CY)
    @impl(stmts.CZ)
    def ctrl_two_qubit_gate(
        self, emit: EmitStimMain, frame: EmitStimFrame, stmt: ControlledTwoQubitGate
    ):
        controls: tuple[str, ...] = frame.get_values(stmt.controls)
        targets: tuple[str, ...] = frame.get_values(stmt.targets)
        res = f"{self.gate_ctrl_2q_map[stmt.name][int(stmt.dagger)]} " + " ".join(
            f"{ctrl} {tgt}" for ctrl, tgt in zip(controls, targets)
        )
        frame.write_line(res)

        return ()

    @impl(stmts.SPP)
    def spp(self, emit: EmitStimMain, frame: EmitStimFrame, stmt: stmts.SPP):

        targets: tuple[str, ...] = tuple(
            targ.upper() for targ in frame.get_values(stmt.targets)
        )
        if stmt.dagger:
            res = "SPP_DAG " + " ".join(targets)
        else:
            res = "SPP " + " ".join(targets)
        frame.write_line(res)

        return ()
