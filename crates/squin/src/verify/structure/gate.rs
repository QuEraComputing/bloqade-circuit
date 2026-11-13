//! Describe the structure of the gate statements.

use super::{Lending, Nesting, Offset, Place, Structure};
use crate::ir::dialects::gate::for_each_gate;
use crate::ir::dialects::gate::*;

/// Place every gate in a graph, with the default answers for blocks and borrows.
macro_rules! flat {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        placed!(Graph, for $($name),+);
        delegate!(Gate { $($name),+ });
    };
}

for_each_gate!(flat);
