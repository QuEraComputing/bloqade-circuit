//! Write Kirin's structured `if`, `for` and `yield`.

use kirin::prelude::*;
use kirin_interpreter::dialect::Interpretable;
use kirin_scf::{For, If, Yield};

use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::types::SquinType;

/// Run the arm that the condition selects. An `if` passes no inputs to its arms.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for If<SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let arms = [self.then_block(), self.else_block()];
        let results: Vec<SSAValue> = self.results().iter().map(|r| (*r).into()).collect();
        emitter.branch(self.condition(), arms, &[], &results)
    }
}

/// Write the body once, with a test of the index at its head and a branch back at its end.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for For<SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let bounds = [self.start(), self.end(), self.step()];
        let results: Vec<SSAValue> = self.results().iter().map(|r| (*r).into()).collect();
        emitter.counted(bounds, self.body(), self.init_args(), &results)
    }
}

/// Write nothing, because the rule that owns the block copies the yielded values.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Yield<SquinType> {
    fn interpret(&self, _emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        Ok(())
    }
}
