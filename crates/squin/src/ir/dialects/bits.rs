//! Define the bits dialect: the statements on arrays of measurement results.
//!
//! A `Bits` value is immutable, so every statement here is pure.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use crate::ir::macros::{delegate, plain};
use std::marker::PhantomData;

use kirin::prelude::*;

use crate::ir::traits::Threads;
use crate::ir::types::{Length, QuantumTypes};

/// Form a `Bits` value that holds `bits` in operand order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = Ty)]
#[chumsky(format = "$bits_pack {bits} -> {result:type}")]
pub struct BitsPack<Ty: QuantumTypes> {
    pub bits: Vec<SSAValue>,
    #[kirin(type = Ty::bits(Length::Known(bits.len() as u64)))]
    pub result: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Return the measurement result at `index` of `bits`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = Ty)]
#[chumsky(format = "$bits_get {bits}, {index}")]
pub struct BitsGet<Ty: QuantumTypes> {
    pub bits: SSAValue,
    pub index: SSAValue,
    #[kirin(type = Ty::bit())]
    pub bit: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Return the number of measurement results that `bits` holds.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = Ty)]
#[chumsky(format = "$bits_length {bits}")]
pub struct BitsLength<Ty: QuantumTypes> {
    pub bits: SSAValue,
    #[kirin(type = Ty::index())]
    pub length: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Hold one statement of the bits dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(pure, builders, type = Ty)]
pub enum BitsOp<Ty: QuantumTypes> {
    Pack(BitsPack<Ty>),
    Get(BitsGet<Ty>),
    Length(BitsLength<Ty>),
}

delegate!(generic BitsOp { Pack, Get, Length });

plain!(generic Threads, for BitsPack, BitsGet, BitsLength);
