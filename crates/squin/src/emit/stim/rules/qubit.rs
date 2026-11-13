//! Write the qubit and register statements.
//!
//! Stim names every qubit by a fixed index, so each lent or moved element
//! must be a known qubit, even if no gate acts on it.

use kirin_interpreter::dialect::Interpretable;

use super::nothing;
use crate::emit::stim::{EmitStim, StimEmitter, StimError};
use crate::ir::dialects::qubit::{Alloc, Free, Measure, Reset};
use crate::ir::dialects::register::*;

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Alloc {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.allocate(self.wire.into())
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Free {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.release(self.wire)
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Measure {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        let qubit = emitter.index(self.wire)?;
        emitter.instruction("M", &[qubit]);
        Ok(())
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Reset {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        let qubit = emitter.index(self.wire)?;
        emitter.instruction("R", &[qubit]);
        Ok(())
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for AllocRegister {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.allocate(self.register.into())
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for FreeRegister {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.release(self.register)
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for MeasureRegister {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        let qubits = emitter.indices_of(self.register)?;
        emitter.instruction("M", &qubits);
        Ok(())
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Borrow {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.index(self.wire.into())?;
        Ok(())
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Replace {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.index(self.wire_out.into())?;
        Ok(())
    }
}

nothing!(Pack, Split, Join, LengthOf, Release);
