//! Define what a statement sees while the verifier checks it or the runtime runs it.
//!
//! The verifier implements `TypeCheck`, and the runtime `Machine` implements
//! `Evaluator`. The statements name only these traits, so the `ir` and
//! `dialects` modules never import the verifier or the runtime.

mod backend;
mod evaluator;
mod failure;
mod type_check;
mod value;

pub use backend::{Backend, Operation};
pub use evaluator::Evaluator;
pub use failure::Failure;
pub use type_check::TypeCheck;
pub use value::{Qubit, Value};

/// Return `index` as a position in an array of `length` elements.
pub fn position(index: i64, length: usize) -> Result<usize, Failure> {
    let position = usize::try_from(index)
        .ok()
        .filter(|position| *position < length);
    position.ok_or(Failure::Index { index, length })
}
