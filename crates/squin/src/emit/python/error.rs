//! Name the reasons that the Python emitter stops.

use kirin_interpreter::InterpreterError;

use crate::verify::Violation;

/// Tell why the emitter cannot write a function as Python squin code.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum PythonError {
    #[error("The pipeline has no stage named {0}.")]
    UnknownStage(String),
    #[error("The stage has no function named {0}.")]
    UnknownFunction(String),
    #[error("{}", lines(.0))]
    Invalid(Vec<Violation>),
    #[error("The Python emitter has no form for {0}.")]
    Unsupported(String),
    #[error(transparent)]
    Interpreter(#[from] InterpreterError),
}

fn lines(violations: &[Violation]) -> String {
    let lines: Vec<String> = violations.iter().map(Violation::to_string).collect();
    lines.join("\n")
}
