//! Write the register statements.
//!
//! ppvm names every qubit by a fixed index, and the address analysis gives
//! each register element its index. So only allocation, release and
//! measurement write instructions. A lend, a move or a regrouping of
//! elements writes nothing.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::dialects::register::*;

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for AllocRegister {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        emitter.allocate(self.register.into())
    }
}

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for FreeRegister {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        Ok(emitter.qubits.release(self.register)?)
    }
}

/// Measure each qubit of the register and store each outcome in its own slot.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for MeasureRegister {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let qubits = emitter.qubits.indices_of(self.register)?;
        let slots = emitter.define(self.results.into())?;
        for (qubit, slot) in qubits.into_iter().zip(slots) {
            emitter.measure(qubit, slot);
        }
        Ok(())
    }
}

/// Check that the lent element has a known qubit.
///
/// A later gate on the wire needs the index, so the rule reports an unknown
/// element at the statement that lends it.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Borrow {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        emitter.qubits.index(self.wire.into())?;
        Ok(())
    }
}

/// Check that the moved element has a known qubit.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Replace {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        emitter.qubits.index(self.wire_out.into())?;
        Ok(())
    }
}

/// Write the length of the register, which the address analysis knows, as a constant.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for LengthOf {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let length = emitter.qubits.indices_of(self.register)?.len();
        emitter.line(format!("cpu::cpu.const i64, {length}"));
        emitter.result(self.length.into())
    }
}

/// Write nothing for a statement that only regroups qubits.
macro_rules! regroup {
    ($($statement:ident),+) => {$(
        impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for $statement {
            fn interpret(&self, _emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
                Ok(())
            }
        }
    )+};
}

regroup!(Pack, Split, Join, Release);
