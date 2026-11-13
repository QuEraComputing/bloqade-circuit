//! Write the register statements.
//!
//! ppvm names every qubit by a fixed index, and the address analysis gives
//! each register element its index. So only allocation, release and
//! measurement write instructions. A lend, a move or a regrouping of
//! elements writes nothing.

use kirin_interpreter::dialect::Interpretable;

use crate::analysis::address::Address;
use crate::emit::ppvm::operand::Operand;
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
            emitter.measure(Operand::Fixed(qubit), slot);
        }
        Ok(())
    }
}

/// Lend the element at the index to the wire.
///
/// If the address analysis knows the qubit of the lent wire, the rule writes
/// nothing, and gates push its index as a constant. Otherwise the index is
/// known only at run time, and the program reads the qubit index from the
/// register table.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Borrow {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let wire = self.wire.into();
        if emitter.qubits.index(wire).is_ok() {
            return Ok(());
        }
        emitter.borrow_at_run_time(self.register, self.index, wire)
    }
}

/// Check that the analysis knows the index and the qubit of the moved element.
///
/// A `replace` changes which qubits a register holds, and the emitter frees
/// qubits by their fixed index. So a `replace` at a run-time index is an error.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Replace {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        if !matches!(emitter.addresses.of(self.index), Address::Int(_)) {
            return Err(PpvmError::Unsupported(
                "a `replace` at an index that is known only at run time".into(),
            ));
        }
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
