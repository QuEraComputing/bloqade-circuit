//! Describe the structure of the single-qubit statements.

use super::{Lending, Nesting, Offset, Structure};
use crate::ir::macros::plain;
use crate::ir::ops::{Alloc, Free, Measure, QubitOp, Reset};

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

plain!(Structure, for Alloc, Free, Measure, Reset);
