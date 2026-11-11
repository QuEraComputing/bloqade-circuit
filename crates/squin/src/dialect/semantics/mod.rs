//! Define the run-time values, failures and backend operations of squin.
//!
//! The statements describe their execution in these terms. The runtime
//! re-exports them, so a user names them as `squin::runtime::Value`.

mod backend;
mod failure;
mod value;

pub use backend::{Backend, Operation};
pub use failure::Failure;
pub use value::{Qubit, Value};

/// Return `index` as a position in an array of `length` elements.
pub fn position(index: i64, length: usize) -> Result<usize, Failure> {
    let position = usize::try_from(index)
        .ok()
        .filter(|position| *position < length);
    position.ok_or(Failure::Index { index, length })
}
