//! Write squin's `circuit`, `conditional` and `repeat` statements.

use kirin::prelude::*;
use kirin_interpreter::dialect::Interpretable;

use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::dialects::circuit::Circuit;
use crate::ir::dialects::conditional::Conditional;
use crate::ir::dialects::repeat::Repeat;

/// Run the rules of the graph nodes in dependency order.
///
/// Each port shares the slots of its input, and each result shares the slots
/// of the value that the graph yields at its position.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Circuit {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let ports = self.body.expect_info(emitter.program).ports().to_vec();
        for (port, input) in ports.into_iter().zip(&self.inputs) {
            emitter.alias(port.into(), *input)?;
        }
        emitter.graph(self.body)?;
        let yields = self.body.expect_info(emitter.program).yields().to_vec();
        for (result, value) in self.results.iter().zip(yields) {
            emitter.alias((*result).into(), value)?;
        }
        Ok(())
    }
}

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Conditional {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let arms = [self.then_body, self.else_body];
        let results: Vec<SSAValue> = self.results.iter().map(|r| (*r).into()).collect();
        emitter.branch(self.condition, arms, &self.inputs, &results)
    }
}

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Repeat {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let results: Vec<SSAValue> = self.results.iter().map(|r| (*r).into()).collect();
        emitter.repeat_loop(self.body, &self.inputs, &results)
    }
}
