//! Describe the structure of the gate statements.

use super::{Lending, Nesting, Offset, Structure};
use crate::ir::dialects::gate::for_each_gate;
use crate::ir::macros::plain;
use crate::ir::ops::*;

/// Give every gate the default answers, because a gate owns no block and lends no element.
macro_rules! flat {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        plain!(Structure, for $($name),+);
        delegate!(Gate { $($name),+ });
    };
}

for_each_gate!(flat);
