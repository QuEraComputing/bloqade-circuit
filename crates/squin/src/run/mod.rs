//! Evaluate a squin kernel against a backend.
//!
//! The [`Machine`] computes the classical values and the register indices of a
//! kernel. It hands each quantum operation to a [`Backend`] with the qubits that
//! the operation acts on.

mod backend;
mod failure;
mod machine;
mod value;

pub use backend::{Backend, Operation};
pub use failure::Failure;
pub use machine::{Execute, Machine, position};
pub use value::{Qubit, Value};
