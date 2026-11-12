//! Define the bits dialect: the statements on arrays of measurement results.
//!
//! A `Bits` value is immutable, so every statement here is pure.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use crate::ir::macros::{delegate, plain};
use kirin::prelude::*;
use kirin_arith::ArithType;

use crate::ir::traits::Threads;
use crate::ir::types::{Length, SquinType};

/// Form a `Bits` value that holds `bits` in operand order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$bits_pack {bits} -> {result:type}")]
pub struct BitsPack {
    pub bits: Vec<SSAValue>,
    #[kirin(type = SquinType::Bits(Length::Known(bits.len() as u64)))]
    pub result: ResultValue,
}

/// Return the measurement result at `index` of `bits`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$bits_get {bits}, {index}")]
pub struct BitsGet {
    pub bits: SSAValue,
    pub index: SSAValue,
    #[kirin(type = SquinType::Bit)]
    pub bit: ResultValue,
}

/// Return the number of measurement results that `bits` holds.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$bits_length {bits}")]
pub struct BitsLength {
    pub bits: SSAValue,
    #[kirin(type = SquinType::Number(ArithType::I64))]
    pub length: ResultValue,
}

/// Hold one statement of the bits dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(pure, builders, type = SquinType)]
pub enum BitsOp {
    Pack(BitsPack),
    Get(BitsGet),
    Length(BitsLength),
}

delegate!(BitsOp { Pack, Get, Length });

plain!(Threads, for BitsPack, BitsGet, BitsLength);
