//! Define the trait that follows a qubit or a register through a statement.
//!
//! The verifier, the rewrite passes and the analyses all read `Threads`, so it
//! belongs to the definition of a statement.

use kirin::prelude::{ResultValue, SSAValue};
use smallvec::SmallVec;

/// Hold the pairs of a statement. Most statements have one pair or two.
pub type Pairs = SmallVec<[(SSAValue, ResultValue); 2]>;

/// Tell which result of a statement continues which linear operand.
///
/// A pair `(operand, result)` states that both values name the same qubit or
/// the same register. For example, `%b = h %a` pairs `%a` with its result.
pub trait Threads {
    /// Return each linear operand with the result that continues it.
    ///
    /// The default is for a statement that continues none of its operands.
    fn threads(&self) -> Pairs {
        Pairs::new()
    }
}
