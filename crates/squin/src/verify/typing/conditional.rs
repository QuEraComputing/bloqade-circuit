//! State the types of the conditional.

use super::Typed;
use crate::ir::dialects::conditional::Conditional;
use crate::ir::types::SquinType;
use crate::verify::TypeCheck;

/// Check that each arm receives the inputs and yields the types of the results.
///
/// The condition is a `Bool`, so a program reads a measurement with `is_one`,
/// `is_zero` or `is_lost` and decides what a lost atom means.
impl Typed for Conditional {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.condition, SquinType::Bool);
        for arm in [self.then_body, self.else_body] {
            let arguments = typing.arguments(arm);
            if typing.arity(self.inputs.len(), arguments.len()) {
                typing.flows(&self.inputs, &arguments);
            }
            typing.flows(&typing.yields(arm), &self.results);
        }
    }
}
