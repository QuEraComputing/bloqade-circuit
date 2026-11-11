//! Evaluate a squin kernel against a backend.
//!
//! The [`Machine`] computes the classical values and the register indices of a
//! kernel. It hands each quantum operation to a [`Backend`] with the qubits that
//! the operation acts on.

mod machine;
pub mod stim;

pub use crate::dialect::semantics::{Backend, Failure, Operation, Qubit, Value, position};
pub use crate::dialect::traits::{Evaluator, Execute};
pub use machine::Machine;
