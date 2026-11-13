//! State the types of the repeat loop.

use super::Typed;
use crate::ir::dialects::repeat::Repeat;
use crate::ir::types::SquinType;
use crate::verify::TypeCheck;

/// Check that the body receives and yields the types that it carries.
///
/// The body yields a stop flag first, a `Bool`.
impl Typed for Repeat {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let arguments = typing.arguments(self.body);
        if typing.arity(self.inputs.len(), arguments.len()) {
            typing.flows(&self.inputs, &arguments);
            typing.flows(&arguments, &self.results);
        }
        let yields = typing.yields(self.body);
        if !typing.arity(self.inputs.len() + 1, yields.len()) {
            return;
        }
        let (stop, carried) = yields.split_first().unwrap();
        typing.expect(*stop, SquinType::Bool);
        typing.flows(carried, &arguments);
    }
}
