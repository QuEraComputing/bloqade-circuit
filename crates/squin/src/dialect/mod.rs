//! Compose the squin dialects with functions, constants, arithmetic and control flow.

mod adapters;
pub mod bits;
pub mod gate;
pub(crate) mod macros;
pub(crate) mod semantics;
pub mod state;
pub mod traits;
pub mod types;

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::StructuredControlFlow;

use crate::dialect::bits::BitsOp;
use crate::dialect::gate::Gate;
use crate::dialect::macros::delegate;
use crate::dialect::state::State;
use crate::dialect::types::{Scalar, SquinType};

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

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    State,
    Gate,
    Bits,
});
