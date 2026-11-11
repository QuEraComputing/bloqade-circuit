//! Define the statements on single qubits.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::macros::plain;
use crate::run::{Backend, Execute, Failure, Machine, Value};
use crate::threads::{Pairs, Threads};
use crate::types::SquinType;
use crate::verify::{Structure, Typed, Typing};

use smallvec::smallvec;

/// Allocate one qubit in the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$alloc -> {wire:type}")]
pub struct Alloc {
    pub wire: ResultValue,
}

/// End the life of the qubit of `wire`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$free {wire}")]
pub struct Free {
    pub wire: SSAValue,
}

/// Measure the qubit of `wire` and keep the qubit.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$measure {wire} -> {wire_out:type}, {bit:type}")]
pub struct Measure {
    pub wire: SSAValue,
    pub wire_out: ResultValue,
    pub bit: ResultValue,
}

/// Reset the qubit of `wire` to the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$reset {wire} -> {wire_out:type}")]
pub struct Reset {
    pub wire: SSAValue,
    pub wire_out: ResultValue,
}

plain!(Threads, for Alloc, Free);
plain!(Structure, for Alloc, Free, Measure, Reset);

impl Threads for Measure {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

impl Threads for Reset {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

impl Typed for Alloc {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.wire, SquinType::Wire);
    }
}

impl Typed for Free {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.wire, SquinType::Wire);
    }
}

impl Typed for Measure {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.wire, SquinType::Wire);
        typing.expect(self.wire_out, SquinType::Wire);
        typing.expect(self.bit, SquinType::Bit);
    }
}

impl Typed for Reset {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.wire, SquinType::Wire);
        typing.expect(self.wire_out, SquinType::Wire);
    }
}

impl Execute for Alloc {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let qubit = machine.backend().alloc()?;
        machine.write(self.wire, Value::Wire(qubit));
        Ok(())
    }
}

impl Execute for Free {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let qubit = machine.wire(self.wire)?;
        machine.backend().free(qubit)
    }
}

impl Execute for Measure {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let qubit = machine.wire(self.wire)?;
        let mut results = machine.backend().measure(&[qubit])?;
        let (expected, found) = (1, results.len());
        let result = results.pop().ok_or(Failure::Arity { expected, found })?;
        machine.write(self.wire_out, Value::Wire(qubit));
        machine.write(self.bit, Value::Bit(result));
        Ok(())
    }
}

impl Execute for Reset {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let qubit = machine.wire(self.wire)?;
        machine.backend().reset(qubit)?;
        machine.write(self.wire_out, Value::Wire(qubit));
        Ok(())
    }
}
