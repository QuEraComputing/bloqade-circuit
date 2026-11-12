//! Describe the structure of the single-qubit statements.

use super::{Lending, Nesting, Offset, Structure};
use crate::ir::dialects::qubit::{Alloc, Free, Measure, QubitOp, Reset};
use crate::ir::macros::plain;

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

plain!(Structure, for Alloc, Free, Measure, Reset);
