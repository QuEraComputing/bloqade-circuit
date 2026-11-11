//! Define the Squin rules for Kirin loops.

use kirin_scf::For;

use crate::ir::contexts::{Evaluator, TypeCheck};
use crate::ir::contexts::{Failure, Value};
use crate::ir::traits::macros::plain;
use crate::ir::traits::{Execute, Nesting, Structure, Threads, Typed};
use crate::ir::types::SquinType;

plain!(Threads, for For<SquinType>);

/// Check that the loop body receives and yields the types that it carries.
impl Typed for For<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(
            [self.induction_var(), self.start(), self.end(), self.step()],
            SquinType::Int,
        );
        let arguments = typing.arguments(self.body());
        if !typing.arity(self.init_args().len() + 1, arguments.len()) {
            return;
        }
        let (index, carried) = arguments.split_first().unwrap();
        typing.exact(*index, SquinType::Int);
        typing.flows(self.init_args(), carried);
        typing.flows(&typing.yields(self.body()), carried);
        typing.flows(carried, self.results());
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
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
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
