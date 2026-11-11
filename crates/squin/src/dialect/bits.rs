//! Define the statements on arrays of measurement results.
//!
//! A `Bits` value is immutable, so every statement here is pure.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::dialect::macros::{delegate, plain};
use crate::dialect::semantics::{Failure, Value, position};
use crate::dialect::traits::{Evaluator, Execute, Structure, Threads, TypeCheck, Typed};
use crate::dialect::types::{Length, SquinType};

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

impl Typed for BitsPack {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(self.bits.iter().copied(), SquinType::Bit);
        let length = Length::Known(self.bits.len() as u64);
        typing.covers(self.result, SquinType::Bits(length));
    }
}

impl Typed for BitsGet {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.bits, SquinType::Bits(Length::Any));
        typing.expect(self.index, SquinType::Int);
        typing.expect(self.bit, SquinType::Bit);
    }
}

impl Typed for BitsLength {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.bits, SquinType::Bits(Length::Any));
        typing.expect(self.length, SquinType::Int);
    }
}

impl Execute for BitsPack {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let results = self.bits.iter().map(|bit| match machine.read(*bit)? {
            Value::Bit(result) => Ok(result),
            other => Err(other.is_not("a measurement result")),
        });
        let results = results.collect::<Result<_, _>>()?;
        machine.write(self.result, Value::Bits(results));
        Ok(())
    }
}

impl Execute for BitsGet {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let results = machine.results(self.bits)?;
        let index = position(machine.int(self.index)?, results.len())?;
        machine.write(self.bit, Value::Bit(results[index].clone()));
        Ok(())
    }
}

impl Execute for BitsLength {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let count = machine.results(self.bits)?.len();
        machine.write(self.length, Value::Int(count as i64));
        Ok(())
    }
}
