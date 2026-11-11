//! State what a statement does when it runs.

use crate::ir::contexts::{Evaluator, Failure};

/// Carry out one statement on an evaluator.
pub trait Execute {
    /// Read the operands of the statement from `machine` and write its results.
    ///
    /// The default is for a statement that does nothing when it runs, such as a
    /// terminator. The evaluator reads the operands of a terminator itself.
    fn execute<E: Evaluator>(&self, _machine: &mut E) -> Result<(), Failure> {
        Ok(())
    }
}
