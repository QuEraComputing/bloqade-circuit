//! Write the qubit statements: allocation, release, measurement and reset.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::python::{EmitPython, PythonEmitter, PythonError};
use crate::ir::dialects::qubit::{Alloc, Free, Measure, Reset};

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Alloc {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        emitter.assign(self.wire.into(), "squin.qalloc(1)[0]")
    }
}

/// Write nothing, because Python squin has no statement that frees a qubit.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Free {
    fn interpret(&self, _emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        Ok(())
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Measure {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let qubit = emitter.text(self.wire)?;
        emitter.assign(self.result.into(), &format!("squin.measure({qubit})"))?;
        emitter.alias(self.wire_out.into(), self.wire)
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Reset {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let qubit = emitter.text(self.wire)?;
        emitter.line(format!("squin.reset({qubit})"));
        emitter.continue_wires(self)
    }
}
