//! Define the register dialect: the statements on arrays of qubits.
//!
//! A `borrow` takes one element out, and a `release` puts it back. Every other
//! statement needs a register with every element in place.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use std::marker::PhantomData;

use kirin::prelude::*;
use smallvec::smallvec;

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Pairs, Threads};

use crate::ir::types::{Length, QuantumTypes};

/// Allocate `size` qubits in the zero state as one register.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$alloc_register {size} -> {register:type}")]
pub struct AllocRegister<Ty: QuantumTypes> {
    pub size: SSAValue,
    pub register: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// End the life of every qubit of `register`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$free_register {register}")]
pub struct FreeRegister<Ty: QuantumTypes> {
    pub register: SSAValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Consume `wires` and form a register that holds them in operand order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$pack {wires} -> {register:type}")]
pub struct Pack<Ty: QuantumTypes> {
    pub wires: Vec<SSAValue>,
    #[kirin(type = Ty::register(Length::Known(wires.len() as u64)))]
    pub register: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Divide `register` into the elements before `index` and the other elements.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$split {register}, {index} -> {before:type}, {after:type}")]
pub struct Split<Ty: QuantumTypes> {
    pub register: SSAValue,
    pub index: SSAValue,
    pub before: ResultValue,
    pub after: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Consume two registers and form one register of `first` and then `second`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$join {first}, {second} -> {register:type}")]
pub struct Join<Ty: QuantumTypes> {
    pub first: SSAValue,
    pub second: SSAValue,
    pub register: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Return `register` and the number of qubits that it holds.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$length {register} -> {register_out:type}")]
pub struct LengthOf<Ty: QuantumTypes> {
    pub register: SSAValue,
    pub register_out: ResultValue,
    #[kirin(type = Ty::index())]
    pub length: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Measure every qubit of `register` and return the results in element order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$measure_register {register} -> {register_out:type}, {bits:type}")]
pub struct MeasureRegister<Ty: QuantumTypes> {
    pub register: SSAValue,
    pub register_out: ResultValue,
    pub bits: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Lend the qubit at `index` of `register` to a wire.
///
/// The element stays empty until a `release` consumes `slot`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$borrow {register}, {index} -> {register_out:type}")]
pub struct Borrow<Ty: QuantumTypes> {
    pub register: SSAValue,
    pub index: SSAValue,
    pub register_out: ResultValue,
    #[kirin(type = Ty::slot())]
    pub slot: ResultValue,
    #[kirin(type = Ty::wire())]
    pub wire: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Put the qubit of `wire` back into the element that `slot` names.
///
/// The wire must carry the qubit that the `borrow` of `slot` took out.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$release {register}, {slot}, {wire} -> {register_out:type}")]
pub struct Release<Ty: QuantumTypes> {
    pub register: SSAValue,
    pub slot: SSAValue,
    pub wire: SSAValue,
    pub register_out: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Put the qubit of `wire` at `index` and return the qubit that was there.
///
/// This is the statement that moves a qubit to a new register position.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$replace {register}, {index}, {wire} -> {register_out:type}")]
pub struct Replace<Ty: QuantumTypes> {
    pub register: SSAValue,
    pub index: SSAValue,
    pub wire: SSAValue,
    pub register_out: ResultValue,
    #[kirin(type = Ty::wire())]
    pub wire_out: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Hold one statement of the register dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(builders, type = Ty)]
pub enum RegisterOp<Ty: QuantumTypes> {
    AllocRegister(AllocRegister<Ty>),
    FreeRegister(FreeRegister<Ty>),
    Pack(Pack<Ty>),
    Split(Split<Ty>),
    Join(Join<Ty>),
    LengthOf(LengthOf<Ty>),
    MeasureRegister(MeasureRegister<Ty>),
    Borrow(Borrow<Ty>),
    Release(Release<Ty>),
    Replace(Replace<Ty>),
}

delegate!(generic RegisterOp {
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

plain!(generic Threads, for AllocRegister, FreeRegister, Pack, Split, Join);

impl<Ty: QuantumTypes> Threads for LengthOf<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl<Ty: QuantumTypes> Threads for MeasureRegister<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl<Ty: QuantumTypes> Threads for Borrow<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl<Ty: QuantumTypes> Threads for Release<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}

impl<Ty: QuantumTypes> Threads for Replace<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.register, self.register_out)]
    }
}
