//! Check the types of the gate statements.

use kirin::prelude::*;

use super::{TypeCheck, Typed};
use crate::ir::dialects::gate::*;
use crate::ir::traits::Threads;
use crate::ir::types::SquinType;

/// Require each angle of a gate to be a `Float` and each wire to be a `Wire`.
macro_rules! typed {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        $(impl Typed for $name {
            fn check<C: TypeCheck>(&self, typing: &mut C) {
                let angles: &[SSAValue] = &[$($(self.$angle),+)?];
                typing.each(angles.iter().copied(), SquinType::Float);
                for (wire, wire_out) in self.threads() {
                    typing.expect(wire, SquinType::Wire);
                    typing.expect(wire_out, SquinType::Wire);
                }
            }
        })+

        delegate!(Gate { $($name),+ });
    };
}

for_each_gate!(typed);
