//! Write the statements of the measurement dialect.
//!
//! ppvm encodes an outcome as a `u32`: 0 for zero, 1 for one and 2 for a lost atom.

use kirin::prelude::*;
use kirin_interpreter::dialect::Interpretable;

use super::unsupported;
use crate::analysis::address::Address;
use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::dialects::measurement::*;

/// Compare the outcome in the slot of `result` with `code` and store the answer.
fn outcome(
    emitter: &mut PpvmEmitter<'_>,
    result: SSAValue,
    answer: SSAValue,
    code: u32,
) -> Result<(), PpvmError> {
    emitter.load(result)?;
    emitter.line(format!("cpu::cpu.const u32, {code}"));
    emitter.line("cpu::cpu.eq u32".to_string());
    emitter.result(answer)
}

/// Write the rule of each outcome test with the code that it compares against.
macro_rules! outcome_tests {
    ($($statement:ident => $code:literal),+) => {$(
        impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for $statement {
            fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
                outcome(emitter, self.result, self.answer.into(), $code)
            }
        }
    )+};
}

outcome_tests!(IsZero => 0, IsOne => 1, IsLost => 2);

/// Let the packed list use the slots of its results in order.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for PackResults {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let slots = self.results.iter().map(|result| emitter.slots_of(*result));
        let slots = slots.collect::<Result<Vec<_>, _>>()?.concat();
        emitter.set(self.packed.into(), slots)
    }
}

/// Let the result use the slot at the index, which the address analysis must know.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for GetResult {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let Address::Int(index) = emitter.addresses.of(self.index) else {
            return Err(unsupported(
                "`get_result` at an index that the analysis does not know",
            ));
        };
        let slots = emitter.slots_of(self.results)?;
        let slot = usize::try_from(index)
            .ok()
            .and_then(|index| slots.get(index).copied());
        let slot = slot.ok_or_else(|| unsupported("`get_result` past the end"))?;
        emitter.set(self.result.into(), vec![slot])
    }
}

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for ResultsLength {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let count = emitter.slots_of(self.results)?.len();
        emitter.line(format!("cpu::cpu.const i64, {count}"));
        emitter.result(self.length.into())
    }
}
