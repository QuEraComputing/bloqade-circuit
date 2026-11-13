//! Describe the structure of the single-qubit statements.

use super::{Lending, Nesting, Offset, Place, Structure};
use crate::ir::dialects::qubit::{Alloc, Free, Measure, QubitOp, Reset};

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

placed!(Anywhere, for Alloc, Free);
placed!(Graph, for Measure, Reset);
