//! Define the statements on arrays of measurement results.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::types::SquinType;

/// Build and read `Bits` values, which are immutable.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
pub enum BitsOp {
    /// Form a `Bits` value that holds `bits` in operand order.
    #[chumsky(format = "$bits_pack {bits} -> {result:type}")]
    Pack {
        bits: Vec<SSAValue>,
        result: ResultValue,
    },

    /// Return the measurement result at `index` of `bits`.
    #[chumsky(format = "$bits_get {bits}, {index} -> {bit:type}")]
    Get {
        bits: SSAValue,
        index: SSAValue,
        bit: ResultValue,
    },

    /// Return the number of measurement results that `bits` holds.
    #[chumsky(format = "$bits_length {bits} -> {length:type}")]
    Length { bits: SSAValue, length: ResultValue },
}
