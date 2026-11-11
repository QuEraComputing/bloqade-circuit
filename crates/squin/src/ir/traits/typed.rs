//! State the type rule of a statement.

use crate::ir::contexts::TypeCheck;

/// State the types that a statement needs for its operands and results.
pub trait Typed {
    /// Check the types of the statement and record each mismatch in `typing`.
    ///
    /// The default is for a statement that accepts every type.
    fn check<C: TypeCheck>(&self, _typing: &mut C) {}
}
