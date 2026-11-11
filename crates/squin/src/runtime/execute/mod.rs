//! Define what each statement does when it runs.
//!
//! Each file holds the execution of one dialect.

/// Implement `Execute` for an enum that wraps one statement in each variant.
macro_rules! delegate {
    ($wrapper:ty { $($variant:ident),+ $(,)? }) => {
        impl $crate::runtime::Execute for $wrapper {
            fn execute<E: $crate::runtime::Evaluator>(
                &self,
                machine: &mut E,
            ) -> Result<(), $crate::runtime::Failure> {
                match self {
                    $(Self::$variant(inner) => inner.execute(machine),)+
                }
            }
        }
    };
}

mod bits;
mod from_kirin;
mod gate;
mod qubit;
mod register;

use super::{Evaluator, Failure};
use crate::ir::Squin;

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

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    Qubit,
    Register,
    Gate,
    Bits,
});
