//! Define the squin dialects and compose them with the Kirin dialects into `Squin`.
//!
//! Each dialect is one module with its statements and their trait impls.
//! `from_kirin` holds the squin trait impls for the Kirin statements that `Squin` uses.

pub mod bits;
mod from_kirin;
pub mod gate;
pub mod qubit;
pub mod register;

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::StructuredControlFlow;

use crate::ir::traits::macros::delegate;
use crate::ir::types::{Scalar, SquinType};
use bits::BitsOp;
use gate::Gate;
use qubit::QubitOp;
use register::RegisterOp;

/// Hold one statement of a squin kernel.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
pub enum Squin {
    #[wraps]
    Function(Function<SquinType>),
    #[wraps]
    Return(Return<SquinType>),
    #[wraps]
    Structured(StructuredControlFlow<SquinType>),
    #[wraps]
    Constant(Constant<Scalar, SquinType>),
    #[wraps]
    Arith(Arith<SquinType>),
    #[wraps]
    Cmp(Cmp<SquinType>),
    #[wraps]
    Qubit(QubitOp),
    #[wraps]
    Register(RegisterOp),
    #[wraps]
    Gate(Gate),
    #[wraps]
    Bits(BitsOp),
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
