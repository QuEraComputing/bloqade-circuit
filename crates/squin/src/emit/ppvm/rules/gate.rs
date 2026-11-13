//! Write each squin gate as one ppvm circuit instruction, or `cy` as three.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::dialects::gate::*;

/// Write the rule of each gate that maps to one ppvm instruction.
///
/// An entry `Gate => "name" (angle, ..)` writes the instruction `name` and
/// pushes the listed angle fields after the qubits.
macro_rules! direct {
    ($($gate:ident => $name:literal $(($($angle:ident),+))?;)+) => {$(
        impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for $gate {
            fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
                emitter.gate(self, $name, &[$($(self.$angle),+)?])
            }
        }
    )+};
}

direct! {
    X => "x";
    Y => "y";
    Z => "z";
    H => "h";
    S => "s";
    SDag => "s_adj";
    T => "t";
    TDag => "t_adj";
    SqrtX => "sqrt_x";
    SqrtXDag => "sqrt_x_adj";
    SqrtY => "sqrt_y";
    SqrtYDag => "sqrt_y_adj";
    Rx => "rx" (angle);
    Ry => "ry" (angle);
    Rz => "rz" (angle);
    U3 => "u3" (theta, phi, lam);
    CX => "cnot";
    CZ => "cz";
}

/// Write `cy` as `s_adj` on the target, `cnot`, and `s` on the target.
///
/// ppvm has no `cy`. The phase gates turn the Y axis of the target into its
/// X axis and back, so `cy = s · cnot · s_adj` on the target.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for CY {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let qubits = emitter.operands(self)?;
        let target = &qubits[1..];
        emitter.qubit_instruction("s_adj", target);
        emitter.qubit_instruction("cnot", &qubits);
        emitter.qubit_instruction("s", target);
        emitter.continue_wires(self)
    }
}
