//! Compose the squin dialects with the Kirin dialects into one language.

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::StructuredControlFlow;

use crate::ir::dialects::bits::BitsOp;
use crate::ir::dialects::gate::Gate;
use crate::ir::dialects::qubit::QubitOp;
use crate::ir::dialects::register::RegisterOp;
use crate::ir::macros::delegate;
use crate::ir::types::{Scalar, SquinType};

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
