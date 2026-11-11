//! Define the register dialect: the statements on arrays of qubits.
//!
//! `whole` holds the statements on registers with every element in place.
//! `borrow` holds the statements that take one element out and put it back.

mod borrow;
mod whole;

use kirin::prelude::*;

use crate::ir::traits::macros::delegate;
use crate::ir::types::SquinType;
pub use borrow::{Borrow, Release, Replace};
pub use whole::{AllocRegister, FreeRegister, Join, LengthOf, MeasureRegister, Pack, Split};

/// Hold one statement of the register dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(builders, type = SquinType)]
pub enum RegisterOp {
    AllocRegister(AllocRegister),
    FreeRegister(FreeRegister),
    Pack(Pack),
    Split(Split),
    Join(Join),
    LengthOf(LengthOf),
    MeasureRegister(MeasureRegister),
    Borrow(Borrow),
    Release(Release),
    Replace(Replace),
}

delegate!(RegisterOp {
    AllocRegister,
    FreeRegister,
    Pack,
    Split,
    Join,
    LengthOf,
    MeasureRegister,
    Borrow,
    Release,
    Replace,
});
