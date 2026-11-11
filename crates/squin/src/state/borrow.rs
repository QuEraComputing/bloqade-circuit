//! Define the statements that take one element out of a register.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::macros::plain;
use crate::run::{Backend, Execute, Failure, Machine, Value};
use crate::threads::{Pairs, Threads};
use crate::types::SquinType;
use crate::verify::{Structure, Typed, Typing};

use crate::run::position;
use crate::verify::Lending;
use smallvec::smallvec;

/// Lend the qubit at `index` of `register` to a wire.
///
/// The element stays empty until a `release` consumes `slot`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$borrow {register}, {index} -> {register_out:type}, {slot:type}, {wire:type}")]
pub struct Borrow {
    pub register: SSAValue,
    pub index: SSAValue,
    pub register_out: ResultValue,
    pub slot: ResultValue,
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
#[chumsky(format = "$replace {register}, {index}, {wire} -> {register_out:type}, {wire_out:type}")]
pub struct Replace {
    pub register: SSAValue,
    pub index: SSAValue,
    pub wire: SSAValue,
    pub register_out: ResultValue,
    pub wire_out: ResultValue,
}

plain!(Structure, for Replace);

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

impl Structure for Borrow {
    fn lending(&self) -> Option<Lending> {
        Some(Lending::Borrow {
            register: self.register,
            index: self.index,
            register_out: self.register_out,
            slot: self.slot,
            wire: self.wire,
        })
    }
}

impl Structure for Release {
    fn lending(&self) -> Option<Lending> {
        Some(Lending::Release {
            register: self.register,
            slot: self.slot,
            wire: self.wire,
        })
    }
}

impl Typed for Borrow {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.index, SquinType::Int);
        typing.expect(self.slot, SquinType::Slot);
        typing.expect(self.wire, SquinType::Wire);
        if let Some((len, lent)) = typing.register(self.register) {
            let lent = lent + 1;
            typing.exact(self.register_out, SquinType::Register { len, lent });
        }
    }
}

impl Typed for Release {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.slot, SquinType::Slot);
        typing.expect(self.wire, SquinType::Wire);
        match typing.register(self.register) {
            Some((_, 0)) => typing.fail(self.register, "a register with an empty element"),
            Some((len, lent)) => {
                let lent = lent - 1;
                typing.exact(self.register_out, SquinType::Register { len, lent });
            }
            None => {}
        }
    }
}

impl Typed for Replace {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.whole(self.register);
        typing.expect(self.index, SquinType::Int);
        typing.expect(self.wire, SquinType::Wire);
        typing.exact(self.register_out, typing.ty(self.register));
        typing.expect(self.wire_out, SquinType::Wire);
    }
}

impl Execute for Borrow {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let index = position(machine.int(self.index)?, qubits.len())?;
        let qubit = qubits[index].take().ok_or(Failure::Lent { index })?;
        machine.write(self.register_out, Value::Register(qubits));
        machine.write(self.slot, Value::Slot(index));
        machine.write(self.wire, Value::Wire(qubit));
        Ok(())
    }
}

impl Execute for Release {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let index = machine.slot(self.slot)?;
        let qubit = machine.wire(self.wire)?;
        let length = qubits.len();
        let element = qubits.get_mut(index).ok_or(Failure::Index {
            index: index as i64,
            length,
        })?;
        *element = Some(qubit);
        machine.write(self.register_out, Value::Register(qubits));
        Ok(())
    }
}

impl Execute for Replace {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let mut qubits = machine.register(self.register)?;
        let index = position(machine.int(self.index)?, qubits.len())?;
        let old = qubits[index].replace(machine.wire(self.wire)?);
        machine.write(self.register_out, Value::Register(qubits));
        machine.write(
            self.wire_out,
            Value::Wire(old.ok_or(Failure::Lent { index })?),
        );
        Ok(())
    }
}
