//! Write the qubit statements: allocation, release, measurement and reset.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::dialects::qubit::{Alloc, Free, Measure, Reset};

/// Give the new wire a qubit index, and reset that qubit if it can hold a state.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Alloc {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        emitter.allocate(self.wire.into())
    }
}

/// Return the qubit index of the wire to the pool.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Free {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        Ok(emitter.qubits.release(self.wire)?)
    }
}

/// Measure the qubit and store the `u32` outcome in the slot of the result.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Measure {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let qubit = emitter.operand(self.wire)?;
        let slot = emitter.define(self.result.into())?[0];
        emitter.measure(qubit, slot);
        emitter.alias(self.wire_out.into(), self.wire)
    }
}

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Reset {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let qubit = emitter.operand(self.wire)?;
        emitter.qubit_instruction("reset", &[qubit]);
        emitter.continue_wires(self)
    }
}
