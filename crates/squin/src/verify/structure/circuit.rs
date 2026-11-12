//! Describe the blocks of the circuit region.

use super::Structure;
use crate::ir::dialects::circuit::Circuit;

// The region owns a graph and no block, so the block checks see a flat statement.
impl Structure for Circuit {}
