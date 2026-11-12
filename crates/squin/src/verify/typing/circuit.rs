//! State the types of the circuit region.

use super::Typed;
use crate::ir::dialects::circuit::Circuit;

// The parser gives each result the type of its annotation.
impl Typed for Circuit {}
