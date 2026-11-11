//! Define the bits dialect: the statements on arrays of measurement results.
//!
//! A `Bits` value is immutable, so every statement here is pure.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Structure, Threads};
use crate::ir::types::SquinType;

/// Form a `Bits` value that holds `bits` in operand order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$bits_pack {bits} -> {result:type}")]
pub struct BitsPack {
    pub bits: Vec<SSAValue>,
    pub result: ResultValue,
}

/// Return the measurement result at `index` of `bits`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$bits_get {bits}, {index} -> {bit:type}")]
pub struct BitsGet {
    pub bits: SSAValue,
    pub index: SSAValue,
    pub bit: ResultValue,
}

/// Return the number of measurement results that `bits` holds.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$bits_length {bits} -> {length:type}")]
pub struct BitsLength {
    pub bits: SSAValue,
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

plain!(Structure, for BitsPack, BitsGet, BitsLength);
