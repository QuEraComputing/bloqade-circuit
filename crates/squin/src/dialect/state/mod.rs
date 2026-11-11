//! Define the statements that create, move and measure qubits.
//!
//! Every statement consumes its wire and register operands. A statement that
//! keeps a qubit alive returns the next value of that wire or register. Each
//! statement is one struct, and its rules stand next to it.

mod borrow;
mod register;
mod wire;

use kirin::prelude::*;

use crate::dialect::macros::delegate;
use crate::dialect::types::SquinType;
pub use borrow::{Borrow, Release, Replace};
pub use register::{AllocRegister, FreeRegister, Join, LengthOf, MeasureRegister, Pack, Split};
pub use wire::{Alloc, Free, Measure, Reset};

/// Hold one statement of the state dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(builders, type = SquinType)]
pub enum State {
    Alloc(Alloc),
    Free(Free),
    Measure(Measure),
    Reset(Reset),
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

delegate!(State {
    Alloc,
    Free,
    Measure,
    Reset,
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
