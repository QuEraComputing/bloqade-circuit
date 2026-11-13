//! Give the gate statements their forward rules.
//!
//! A gate leaves each qubit in place, so each output wire takes the value of
//! the input wire that it continues.

use kirin_interpreter::dialect::{
    ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp,
};

use crate::ir::dialects::gate::for_each_gate;
use crate::ir::dialects::gate::*;
use crate::ir::traits::Threads;

/// Write the rule of each gate.
macro_rules! forwarded {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        $(impl<I: SparseForwardInterp> Interpretable<I, ForwardEval> for $name {
            fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
                for (wire, wire_out) in self.threads() {
                    let qubit = interp.read(wire)?;
                    interp.write(wire_out, qubit)?;
                }
                Ok(SparseForwardEffect::Next)
            }
        })+
    };
}

for_each_gate!(forwarded);
