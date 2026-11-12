//! Check the types of the gate statements.

use kirin::prelude::*;
use kirin_arith::ArithType;

use super::{TypeCheck, Typed};
use crate::ir::dialects::gate::for_each_gate;
use crate::ir::dialects::gate::*;
use crate::ir::traits::Threads;
use crate::ir::types::SquinType;

/// Require each angle of a gate to be an `f64` and each wire to be a `Wire`.
macro_rules! typed {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        $(impl Typed for $name {
            fn check<C: TypeCheck>(&self, typing: &mut C) {
                let angles: &[SSAValue] = &[$($(self.$angle),+)?];
                typing.each(angles.iter().copied(), SquinType::Number(ArithType::F64));
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
