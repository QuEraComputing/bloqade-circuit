//! Write the statements of the measurement dialect as Python squin calls.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::python::{EmitPython, PythonEmitter, PythonError};
use crate::ir::dialects::measurement::*;

/// Write the rule of each outcome test with its Python squin function.
macro_rules! outcome_tests {
    ($($statement:ident => $name:literal),+) => {$(
        impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for $statement {
            fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
                let result = emitter.text(self.result)?;
                emitter.assign(self.answer.into(), &format!("squin.{}({result})", $name))
            }
        }
    )+};
}

outcome_tests!(IsZero => "is_zero", IsOne => "is_one", IsLost => "is_lost");

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for PackResults {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let results = self.results.iter().map(|result| emitter.text(*result));
        let results = results.collect::<Result<Vec<_>, _>>()?;
        emitter.assign(self.packed.into(), &format!("[{}]", results.join(", ")))
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for GetResult {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (results, index) = (emitter.text(self.results)?, emitter.text(self.index)?);
        emitter.assign(self.result.into(), &format!("{results}[{index}]"))
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for ResultsLength {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let results = emitter.text(self.results)?;
        emitter.assign(self.length.into(), &format!("len({results})"))
    }
}
