//! Define the statements on registers that have every element in place.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::ir::contexts::{Backend, Failure, Value};
use crate::ir::contexts::{Evaluator, TypeCheck};
use crate::ir::traits::macros::plain;
use crate::ir::traits::{Execute, Pairs, Structure, Threads, Typed};
use crate::ir::types::SquinType;

use crate::ir::types::Length;
use smallvec::smallvec;

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
#[chumsky(format = "$length {register} -> {register_out:type}, {length:type}")]
pub struct LengthOf {
    pub register: SSAValue,
    pub register_out: ResultValue,
    pub length: ResultValue,
}

/// Measure every qubit of `register` and return the results in element order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$measure_register {register} -> {register_out:type}, {bits:type}")]
pub struct MeasureRegister {
    pub register: SSAValue,
    pub register_out: ResultValue,
    pub bits: ResultValue,
}

plain!(Threads, for AllocRegister, FreeRegister, Pack, Split, Join);
plain!(Structure, for AllocRegister, FreeRegister, Pack, Split, Join, LengthOf, MeasureRegister);

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

impl Typed for AllocRegister {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.size, SquinType::Int);
        typing.whole(self.register);
    }
}

impl Typed for FreeRegister {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
    }
}

impl Typed for Pack {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(self.wires.iter().copied(), SquinType::Wire);
        let length = Length::Known(self.wires.len() as u64);
        typing.covers(self.register, SquinType::register(length));
    }
}

impl Typed for Split {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
        typing.expect(self.index, SquinType::Int);
        typing.whole(self.before);
        typing.whole(self.after);
    }
}

impl Typed for Join {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.first);
        typing.whole(self.second);
        typing.whole(self.register);
    }
}

impl Typed for LengthOf {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.register(self.register);
        typing.exact(self.register_out, typing.ty(self.register));
        typing.expect(self.length, SquinType::Int);
    }
}

impl Typed for MeasureRegister {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
        typing.exact(self.register_out, typing.ty(self.register));
        if let Some((len, _)) = typing.register(self.register) {
            typing.exact(self.bits, SquinType::Bits(len));
        }
    }
}

impl Execute for AllocRegister {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let size = machine.int(self.size)?;
        let count = usize::try_from(size).map_err(|_| Failure::Size(size))?;
        let qubits = (0..count).map(|_| machine.backend().alloc().map(Some));
        let qubits = qubits.collect::<Result<_, _>>()?;
        machine.write(self.register, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for FreeRegister {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        for qubit in machine.whole(self.register)? {
            machine.backend().free(qubit)?;
        }
        Ok(())
    }
}

impl Execute for Pack {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubits = self.wires.iter().map(|wire| machine.wire(*wire).map(Some));
        let qubits = qubits.collect::<Result<_, _>>()?;
        machine.write(self.register, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for Split {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let (index, length) = (machine.int(self.index)?, qubits.len());
        let cut = usize::try_from(index).ok().filter(|cut| *cut <= length);
        let rest = qubits.split_off(cut.ok_or(Failure::Index { index, length })?);
        machine.write(self.before, Value::Register(qubits));
        machine.write(self.after, Value::Register(rest));
        Ok(())
    }
}

impl Execute for Join {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let mut qubits = machine.register(self.first)?;
        qubits.extend(machine.register(self.second)?);
        machine.write(self.register, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for LengthOf {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubits = machine.register(self.register)?;
        machine.write(self.length, Value::Int(qubits.len() as i64));
        machine.write(self.register_out, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for MeasureRegister {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let qubits = machine.whole(self.register)?;
        let results = machine.backend().measure(&qubits)?;
        let qubits = qubits.into_iter().map(Some).collect();
        machine.write(self.register_out, Value::Register(qubits));
        machine.write(self.bits, Value::Bits(results));
        Ok(())
    }
}
