//! Define the register dialect: the statements on arrays of qubits.
//!
//! A `borrow` takes one element out, and a `release` puts it back. Every other
//! statement needs a register with every element in place.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;
use kirin_arith::ArithType;
use kirin_interpreter::Interpretable;
use smallvec::smallvec;

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Pairs, Threads};
use crate::ir::types::{Length, SquinType};

/// Allocate `size` qubits in the zero state as one register.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$alloc_register {size} -> {register:type}")]
pub struct AllocRegister {
    pub size: SSAValue,
    pub register: ResultValue,
}

/// End the life of every qubit of `register`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$free_register {register}")]
pub struct FreeRegister {
    pub register: SSAValue,
}

/// Consume `wires` and form a register that holds them in operand order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$pack {wires} -> {register:type}")]
pub struct Pack {
    pub wires: Vec<SSAValue>,
    #[kirin(type = SquinType::register(Length::Known(wires.len() as u64)))]
    pub register: ResultValue,
}

/// Divide `register` into the elements before `index` and the other elements.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$split {register}, {index} -> {before:type}, {after:type}")]
pub struct Split {
    pub register: SSAValue,
    pub index: SSAValue,
    pub before: ResultValue,
    pub after: ResultValue,
}

/// Consume two registers and form one register of `first` and then `second`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$join {first}, {second} -> {register:type}")]
pub struct Join {
    pub first: SSAValue,
    pub second: SSAValue,
    pub register: ResultValue,
}

/// Return `register` and the number of qubits that it holds.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$length {register} -> {register_out:type}")]
pub struct LengthOf {
    pub register: SSAValue,
    pub register_out: ResultValue,
    #[kirin(type = SquinType::Number(ArithType::I64))]
    pub length: ResultValue,
}

/// Measure every qubit of `register` and return the results in element order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$measure_register {register} -> {register_out:type}, {results:type}")]
pub struct MeasureRegister {
    pub register: SSAValue,
    pub register_out: ResultValue,
    pub results: ResultValue,
}

/// Lend the qubit at `index` of `register` to a wire.
///
/// The element stays empty until a `release` consumes `slot`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$borrow {register}, {index} -> {register_out:type}")]
pub struct Borrow {
    pub register: SSAValue,
    pub index: SSAValue,
    pub register_out: ResultValue,
    #[kirin(type = SquinType::Slot)]
    pub slot: ResultValue,
    #[kirin(type = SquinType::Wire)]
    pub wire: ResultValue,
}

/// Put the qubit of `wire` back into the element that `slot` names.
///
/// The wire must carry the qubit that the `borrow` of `slot` took out.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$release {register}, {slot}, {wire} -> {register_out:type}")]
pub struct Release {
    pub register: SSAValue,
    pub slot: SSAValue,
    pub wire: SSAValue,
    pub register_out: ResultValue,
}

/// Put the qubit of `wire` at `index` and return the qubit that was there.
///
/// This is the statement that moves a qubit to a new register position.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$replace {register}, {index}, {wire} -> {register_out:type}")]
pub struct Replace {
    pub register: SSAValue,
    pub index: SSAValue,
    pub wire: SSAValue,
    pub register_out: ResultValue,
    #[kirin(type = SquinType::Wire)]
    pub wire_out: ResultValue,
}

/// Hold one statement of the register dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint, Interpretable)]
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

plain!(Threads, for AllocRegister, FreeRegister, Pack, Split, Join);

impl Threads for LengthOf {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl Threads for MeasureRegister {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl Threads for Borrow {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl Threads for Release {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl Threads for Replace {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}
