//! Give each statement in squin its `EmitPython` rule.
//!
//! Each file holds the rules of one group of dialects. A rule binds each
//! result to a Python expression, and it writes a line when the statement
//! acts on a qubit or computes a value.

mod classical;
mod control;
mod gate;
mod measurement;
mod qubit;
mod register;

use kirin::prelude::*;

use super::{PythonEmitter, PythonError};
use crate::ir::traits::Threads;

impl PythonEmitter<'_> {
    /// Let each output wire of `statement` keep the name of the input wire that it continues.
    fn continue_wires(&mut self, statement: &impl Threads) -> Result<(), PythonError> {
        for (wire, wire_out) in statement.threads() {
            self.alias(wire_out.into(), wire)?;
        }
        Ok(())
    }

    /// Return the Python expression of the angle `value` in radians.
    ///
    /// A squin angle is in turns and Python squin reads radians. A constant
    /// angle becomes one literal, and any other angle gets `* math.tau`.
    fn radians(&mut self, value: SSAValue) -> Result<String, PythonError> {
        let py = self.get(value)?;
        Ok(match py.number {
            Some(turns) => format!("{:?}", turns * std::f64::consts::TAU),
            None => {
                self.uses_math = true;
                format!("{} * math.tau", py.text)
            }
        })
    }
}
