//! Give the Kirin function and control flow statements their squin rules.

use kirin::prelude::*;
use kirin_function::{Function, Return};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use crate::macros::{delegate, plain};
use crate::run::{Backend, Execute, Failure, Machine, Value};
use crate::threads::Threads;
use crate::types::SquinType;
use crate::verify::{Nesting, Structure, Typed, Typing};

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

plain!(Threads, for If<SquinType>, For<SquinType>, Yield<SquinType>);
plain!(Threads, for Function<SquinType>, Return<SquinType>);
plain!(Typed, for Yield<SquinType>, Function<SquinType>, Return<SquinType>);
plain!(Structure, for Yield<SquinType>, Function<SquinType>, Return<SquinType>);
plain!(Execute, for Yield<SquinType>, Function<SquinType>, Return<SquinType>);

/// Check that each arm yields the types of the results.
impl Typed for If<SquinType> {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.expect(self.condition(), SquinType::Bool);
        for arm in [self.then_block(), self.else_block()] {
            typing.flows(&typing.yields(arm), self.results());
        }
    }
}

impl Structure for If<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Arms([self.then_block(), self.else_block()])
    }
}

/// Run the arm that the condition selects and bind what the arm yields.
impl Execute for If<SquinType> {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let arm = match machine.read(self.condition())? {
            Value::Bool(true) => self.then_block(),
            Value::Bool(false) => self.else_block(),
            other => return Err(other.is_not("a truth value")),
        };
        let yielded = machine.block(arm, Vec::new())?;
        machine.bind(self.results(), yielded)
    }
}

/// Check that the loop body receives and yields the types that it carries.
impl Typed for For<SquinType> {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.each([self.start(), self.end(), self.step()], SquinType::Int);
        let carried: Vec<SSAValue> = typing.arguments(self.body()).split_off(1);
        typing.flows(self.init_args(), &carried);
        typing.flows(&typing.yields(self.body()), &carried);
        typing.flows(&carried, self.results());
    }
}

impl Structure for For<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Loop {
            body: self.body(),
            initial: self.init_args(),
        }
    }
}

/// Run the loop body once for each index and pass the carried values along.
impl Execute for For<SquinType> {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        let (start, end) = (machine.int(self.start())?, machine.int(self.end())?);
        let step = machine.int(self.step())?;
        let stride = usize::try_from(step).ok().filter(|stride| *stride > 0);
        let stride = stride.ok_or(Failure::Step(step))?;
        let carried = self.init_args().iter().map(|value| machine.read(*value));
        let mut carried = carried.collect::<Result<Vec<_>, _>>()?;
        for index in (start..end).step_by(stride) {
            carried.insert(0, Value::Int(index));
            carried = machine.block(self.body(), carried)?;
        }
        machine.bind(self.results(), carried)
    }
}
