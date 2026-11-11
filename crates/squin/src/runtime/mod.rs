//! Evaluate a squin kernel against a backend.
//!
//! The [`Machine`] computes the classical values and the register indices of a
//! kernel. Each statement states what it does in `execute`, through the
//! [`Evaluator`] trait. The machine hands each quantum operation to a
//! [`Backend`] with the qubits that the operation acts on.

mod backend;
mod evaluator;
mod execute;
mod failure;
mod machine;
pub mod stim;
mod value;

pub use backend::{Backend, Operation};
pub use evaluator::Evaluator;
pub use execute::Execute;
pub use failure::Failure;
pub use machine::Machine;
pub use value::{Qubit, Value};

/// Return `index` as a position in an array of `length` elements.
pub fn position(index: i64, length: usize) -> Result<usize, Failure> {
    let position = usize::try_from(index)
        .ok()
        .filter(|position| *position < length);
    position.ok_or(Failure::Index { index, length })
}
