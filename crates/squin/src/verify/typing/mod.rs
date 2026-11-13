//! Check the operand types and the result types of each statement.
//!
//! Each file holds the type rules of one dialect. The `lent` count of a
//! register type makes this check enforce two rules. A statement on a whole
//! register requires `lent=0`. A loop body returns each register with the
//! `lent` count that it received.

/// Implement `Typed` for an enum that wraps one statement in each variant.
macro_rules! delegate {
    ($wrapper:ty { $($variant:ident),+ $(,)? }) => {
        impl $crate::verify::typing::Typed for $wrapper {
            fn check<C: $crate::verify::TypeCheck>(&self, typing: &mut C) {
                match self {
                    $(Self::$variant(inner) => inner.check(typing),)+
                }
            }
        }
    };
}

mod circuit;
mod conditional;
mod from_kirin;
mod gate;
mod measurement;
mod qubit;
mod register;
mod repeat;

use super::TypeCheck;
use crate::ir::Squin;

/// State the types that a statement needs for its operands and results.
pub trait Typed {
    /// Check the types of the statement and record each mismatch in `typing`.
    ///
    /// The default is for a statement that accepts every type.
    fn check<C: TypeCheck>(&self, _typing: &mut C) {}
}

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    Bitwise,
    Qubit,
    Register,
    Gate,
    Measurement,
    Circuit,
    Conditional,
    Repeat,
});
