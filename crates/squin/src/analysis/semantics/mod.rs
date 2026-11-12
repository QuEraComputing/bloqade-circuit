//! Give each squin statement its `ForwardEval` rule.
//!
//! Each file holds the rules of one dialect. The wrapper enums forward to the
//! statement of each variant.

mod bits;
mod gate;
mod qubit;
mod register;

use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_interpreter::dialect::{ForwardEval, Interpretable, SparseForwardInterp};
use kirin_scf::StructuredControlFlow;

use crate::ir::Squin;
use crate::ir::ops::{BitsOp, Gate, QubitOp, RegisterOp};
use crate::ir::types::{Scalar, SquinType};

/// Implement `ForwardEval` for an enum that wraps one statement in each variant.
///
/// The impl applies to every engine whose value domain gives each wrapped
/// statement its rule.
macro_rules! forward {
    ($wrapper:ty { $($variant:ident: $inner:ty),+ $(,)? }) => {
        impl<I> Interpretable<I, ForwardEval> for $wrapper
        where
            I: SparseForwardInterp,
            $($inner: Interpretable<I, ForwardEval>,)+
        {
            fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
                match self {
                    $(Self::$variant(inner) => inner.interpret(interp),)+
                }
            }
        }
    };
}

pub(super) use forward;

forward!(Squin {
    Function: Function<SquinType>,
    Return: Return<SquinType>,
    Structured: StructuredControlFlow<SquinType>,
    Constant: Constant<Scalar, SquinType>,
    Arith: Arith<SquinType>,
    Cmp: Cmp<SquinType>,
    Qubit: QubitOp,
    Register: RegisterOp,
    Gate: Gate,
    Bits: BitsOp,
});
