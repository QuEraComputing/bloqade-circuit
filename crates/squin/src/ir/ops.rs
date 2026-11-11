//! Name each statement of the squin language with the squin type lattice.
//!
//! The dialects are generic, as in `gate::H<T>`. The squin language uses them
//! with `SquinType`, so `ops::H` is `gate::H<SquinType>`. Code that works on
//! squin programs names the statements through these aliases.

use super::dialects::{bits, gate, qubit, register};
use super::types::SquinType;

pub type QubitOp = qubit::QubitOp<SquinType>;
pub type Alloc = qubit::Alloc<SquinType>;
pub type Free = qubit::Free<SquinType>;
pub type Measure = qubit::Measure<SquinType>;
pub type Reset = qubit::Reset<SquinType>;

pub type RegisterOp = register::RegisterOp<SquinType>;
pub type AllocRegister = register::AllocRegister<SquinType>;
pub type FreeRegister = register::FreeRegister<SquinType>;
pub type Pack = register::Pack<SquinType>;
pub type Split = register::Split<SquinType>;
pub type Join = register::Join<SquinType>;
pub type LengthOf = register::LengthOf<SquinType>;
pub type MeasureRegister = register::MeasureRegister<SquinType>;
pub type Borrow = register::Borrow<SquinType>;
pub type Release = register::Release<SquinType>;
pub type Replace = register::Replace<SquinType>;

pub type BitsOp = bits::BitsOp<SquinType>;
pub type BitsPack = bits::BitsPack<SquinType>;
pub type BitsGet = bits::BitsGet<SquinType>;
pub type BitsLength = bits::BitsLength<SquinType>;

pub type Gate = gate::Gate<SquinType>;

/// Write one alias for each gate of the gate dialect.
macro_rules! gate_aliases {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        $(pub type $name = gate::$name<SquinType>;)+
    };
}

gate::for_each_gate!(gate_aliases);
