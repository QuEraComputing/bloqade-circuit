//! Name the reasons that the Stim emitter stops.

use kirin_interpreter::InterpreterError;

use crate::analysis::address::AddressError;
use crate::verify::Violation;

/// Tell why the emitter cannot write a function as a Stim circuit.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum StimError {
    #[error("The pipeline has no stage named {0}.")]
    UnknownStage(String),
    #[error("{}", lines(.0))]
    Invalid(Vec<Violation>),
    #[error(transparent)]
    Analysis(#[from] AddressError),
    #[error("The wire {0} carries no known qubit.")]
    UnknownQubit(String),
    #[error("Stim has no instruction for {0}.")]
    Unsupported(String),
    #[error(transparent)]
    Interpreter(#[from] InterpreterError),
}

fn lines(violations: &[Violation]) -> String {
    let lines: Vec<String> = violations.iter().map(Violation::to_string).collect();
    lines.join("\n")
}

impl From<crate::emit::qubits::UnknownQubit> for StimError {
    fn from(unknown: crate::emit::qubits::UnknownQubit) -> Self {
        StimError::UnknownQubit(unknown.0)
    }
}
