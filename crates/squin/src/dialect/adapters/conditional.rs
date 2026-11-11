//! Define the Squin rules for Kirin conditional branches.

use kirin_scf::If;

use crate::dialect::macros::plain;
use crate::dialect::semantics::{Failure, Value};
use crate::dialect::traits::{Evaluator, Execute, Nesting, Structure, Threads, TypeCheck, Typed};
use crate::dialect::types::SquinType;

plain!(Threads, for If<SquinType>);

/// Check that each arm yields the types of the results.
impl Typed for If<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.condition(), SquinType::Bool);
        for arm in [self.then_block(), self.else_block()] {
            typing.arity(0, typing.arguments(arm).len());
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
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let arm = match machine.read(self.condition())? {
            Value::Bool(true) => self.then_block(),
            Value::Bool(false) => self.else_block(),
            other => return Err(other.is_not("a truth value")),
        };
        let yielded = machine.block(arm, Vec::new())?;
        machine.bind(self.results(), yielded)
    }
}
