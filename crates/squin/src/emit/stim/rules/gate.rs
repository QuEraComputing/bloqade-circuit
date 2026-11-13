//! Write each Clifford gate as its Stim instruction.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::stim::{EmitStim, StimEmitter, StimError};
use crate::ir::dialects::gate::*;
use crate::ir::traits::Threads;

/// Write the rule of each gate that Stim names, with its Stim name.
macro_rules! clifford {
    ($($gate:ident => $name:literal),+ $(,)?) => {$(
        impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for $gate {
            fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
                let threads = self.threads();
                let qubits = threads.iter().map(|(wire, _)| emitter.index(*wire));
                let qubits = qubits.collect::<Result<Vec<_>, _>>()?;
                emitter.instruction($name, &qubits);
                Ok(())
            }
        }
    )+};
}

clifford! {
    X => "X", Y => "Y", Z => "Z", H => "H", S => "S", SDag => "S_DAG",
    SqrtX => "SQRT_X", SqrtXDag => "SQRT_X_DAG", SqrtY => "SQRT_Y", SqrtYDag => "SQRT_Y_DAG",
    CX => "CX", CY => "CY", CZ => "CZ",
}

/// Report each gate that Stim lacks, because Stim holds Clifford gates only.
macro_rules! non_clifford {
    ($($gate:ident),+ $(,)?) => {$(
        impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for $gate {
            fn interpret(&self, _emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
                Err(StimError::Unsupported(format!("the gate {}", stringify!($gate))))
            }
        }
    )+};
}

non_clifford!(T, TDag, Rx, Ry, Rz, U3);
