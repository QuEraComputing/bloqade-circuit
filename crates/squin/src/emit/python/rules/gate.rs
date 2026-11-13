//! Write each squin gate as a call of the Python squin gate of the same name.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::python::{EmitPython, PythonEmitter, PythonError};
use crate::ir::dialects::gate::*;
use crate::ir::traits::Threads;

/// Write the rule of each gate with its Python name and its angle fields.
///
/// Python squin takes the angles first and the qubits after them, as in
/// `squin.rx(angle, q)`.
macro_rules! gates {
    ($($gate:ident => $name:literal $(($($angle:ident),+))?;)+) => {$(
        impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for $gate {
            fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
                let mut arguments: Vec<String> = Vec::new();
                $($(arguments.push(emitter.radians(self.$angle)?);)+)?
                for (wire, _) in self.threads() {
                    arguments.push(emitter.text(wire)?);
                }
                emitter.line(format!("squin.{}({})", $name, arguments.join(", ")));
                emitter.continue_wires(self)
            }
        }
    )+};
}

gates! {
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
    CX => "cx";
    CY => "cy";
    CZ => "cz";
}
