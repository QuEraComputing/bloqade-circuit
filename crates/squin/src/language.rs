//! Compose the squin dialects with functions, constants, arithmetic and control flow.

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::StructuredControlFlow;

use crate::bits::BitsOp;
use crate::gate::Gate;
use crate::state::State;
use crate::types::{Scalar, SquinType};

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
    State(State),
    #[wraps]
    Gate(Gate),
    #[wraps]
    Bits(BitsOp),
}
