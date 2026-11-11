/// Tell why the evaluator stopped before the end of a kernel.
#[derive(Clone, Debug, PartialEq, thiserror::Error)]
#[non_exhaustive]
pub enum Failure {
    #[error("Argument {position} needs {expected} and received {found}.")]
    ArgumentType {
        position: usize,
        expected: SquinType,
        found: String,
    },
    #[error("More than one live value owns qubit {qubit}.")]
    AliasedQubit { qubit: Qubit },
    /// A statement read a value of another kind than it needs.
    #[error("A statement needs {expected} and received {found}.")]
    Kind {
        expected: &'static str,
        found: &'static str,
    },
    /// A statement read a value that no earlier statement wrote.
    ///
    /// A linear value leaves the evaluator at its first use.
    #[error("No statement gave {0} a value.")]
    Unbound(String),
    /// An index is outside of `0 <= index < length`.
    #[error("The index {index} is outside of a length of {length}.")]
    Index { index: i64, length: usize },
    /// A statement needs the qubit of a register element that is empty.
    #[error("The register element {index} is empty.")]
    Lent { index: usize },
    /// A block received another number of values than it has arguments.
    #[error("A block has {expected} arguments and received {found} values.")]
    Arity { expected: usize, found: usize },
    /// A loop has a step that is zero or negative.
    #[error("A loop has the step {0}, and it must be positive.")]
    Step(i64),
    /// An integer operation has no result.
    #[error("An integer operation divides by zero or exceeds the range of its type.")]
    Arithmetic,
    /// A register size is negative.
    #[error("A register cannot have the size {0}.")]
    Size(i64),
    /// The backend cannot carry out an operation.
    #[error("The {backend} backend has no operation for {operation}.")]
    Unsupported {
        backend: &'static str,
        operation: String,
    },
}
use super::Qubit;
use crate::ir::types::SquinType;
