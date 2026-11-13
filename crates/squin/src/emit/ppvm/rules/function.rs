//! Write Kirin's function statement and its return.

use kirin_function::{Function, Return};
use kirin_interpreter::dialect::Interpretable;

use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::types::SquinType;

/// Write nothing, because the emitter starts at the entry block of the function.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Function<SquinType> {
    fn interpret(&self, _emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        Ok(())
    }
}

/// End `@main`. ppvm reads the measurement record, so the returned value is unused.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Return<SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        emitter.line("cpu::cpu.ret 0".to_string());
        Ok(())
    }
}
