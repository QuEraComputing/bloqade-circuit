use std::fmt;

/// Tell why the evaluator stopped before the end of a kernel.
#[derive(Clone, Debug, PartialEq)]
pub enum Failure {
    /// A statement read a value of another kind than it needs.
    Kind {
        expected: &'static str,
        found: &'static str,
    },
    /// A statement read a value that no earlier statement wrote.
    ///
    /// A linear value leaves the evaluator at its first use.
    Unbound(String),
    /// An index is outside of `0 <= index < length`.
    Index { index: i64, length: usize },
    /// A statement needs the qubit of a register element that is empty.
    Lent { index: usize },
    /// A block received another number of values than it has arguments.
    Arity { expected: usize, found: usize },
    /// A loop has a step that is zero or negative.
    Step(i64),
    /// A register size is negative.
    Size(i64),
    /// The backend cannot carry out an operation.
    Unsupported {
        backend: &'static str,
        operation: String,
    },
}

impl fmt::Display for Failure {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Failure::Kind { expected, found } => {
                write!(f, "A statement needs {expected} and received {found}.")
            }
            Failure::Unbound(name) => write!(f, "No statement gave {name} a value."),
            Failure::Index { index, length } => {
                write!(f, "The index {index} is outside of a length of {length}.")
            }
            Failure::Lent { index } => write!(f, "The register element {index} is empty."),
            Failure::Arity { expected, found } => {
                write!(
                    f,
                    "A block has {expected} arguments and received {found} values."
                )
            }
            Failure::Step(step) => {
                write!(f, "A loop has the step {step}, and it must be positive.")
            }
            Failure::Size(size) => write!(f, "A register cannot have the size {size}."),
            Failure::Unsupported { backend, operation } => {
                write!(f, "The {backend} backend has no operation for {operation}.")
            }
        }
    }
}

impl std::error::Error for Failure {}
