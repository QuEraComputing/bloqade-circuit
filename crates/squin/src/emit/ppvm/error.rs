//! Name the reasons that the ppvm emitter stops.

use kirin_interpreter::InterpreterError;

use crate::analysis::address::AddressError;
use crate::emit::qubits::UnknownQubit;
use crate::verify::Violation;

/// Tell why the emitter cannot write a function as a ppvm program.
#[derive(Debug, thiserror::Error)]
#[non_exhaustive]
pub enum PpvmError {
    #[error("The pipeline has no stage named {0}.")]
    UnknownStage(String),
    #[error("{}", lines(.0))]
    Invalid(Vec<Violation>),
    #[error(transparent)]
    Analysis(#[from] AddressError),
    #[error("The wire {0} carries no known qubit.")]
    UnknownQubit(String),
    #[error("The ppvm emitter has no lowering for {0}.")]
    Unsupported(String),
    #[error("ppvm rejects the program: {0}")]
    Bytecode(String),
    #[error(transparent)]
    Interpreter(#[from] InterpreterError),
}

fn lines(violations: &[Violation]) -> String {
    let lines: Vec<String> = violations.iter().map(Violation::to_string).collect();
    lines.join("\n")
}

impl From<UnknownQubit> for PpvmError {
    fn from(unknown: UnknownQubit) -> Self {
        PpvmError::UnknownQubit(unknown.0)
    }
}
