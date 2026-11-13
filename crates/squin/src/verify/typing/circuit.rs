//! State the types of the circuit region.

use super::Typed;
use crate::ir::dialects::circuit::Circuit;
use crate::verify::TypeCheck;

/// Check that the ports receive the inputs and the yields give the results.
impl Typed for Circuit {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let ports = typing.ports(self.body);
        if typing.arity(self.inputs.len(), ports.len()) {
            typing.flows(&self.inputs, &ports);
        }
        let yields = typing.graph_yields(self.body);
        if typing.arity(self.results.len(), yields.len()) {
            typing.flows(&yields, &self.results);
        }
    }
}
