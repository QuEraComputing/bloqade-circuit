//! Describe the graph of the circuit region.

use super::{Nesting, Structure};
use crate::ir::dialects::circuit::Circuit;

impl Structure for Circuit {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Graph {
            body: self.body,
            inputs: &self.inputs,
        }
    }
}
