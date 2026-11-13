//! Write the regions, branches and loops that Stim can express.
//!
//! Stim has no branches, so a branch needs a condition that the address
//! analysis knows. The rule then writes only the arm that runs.

use kirin_interpreter::dialect::Interpretable;
use kirin_scf::{For, If, Yield};

use super::nothing;
use crate::analysis::address::Address;
use crate::emit::stim::{EmitStim, StimEmitter, StimError};
use crate::ir::dialects::circuit::Circuit;
use crate::ir::dialects::conditional::Conditional;
use crate::ir::dialects::repeat::Repeat;
use crate::ir::types::SquinType;

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Circuit {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        emitter.graph(self.body)
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for If<SquinType> {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        let arm = match emitter.addresses.of(self.condition()) {
            Address::Bool(true) => self.then_block(),
            Address::Bool(false) => self.else_block(),
            _ => {
                let what = "an `if` on a run-time condition";
                return Err(StimError::Unsupported(what.into()));
            }
        };
        emitter.block(arm)
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Conditional {
    fn interpret(&self, emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        let arm = match emitter.addresses.of(self.condition) {
            Address::Bool(true) => self.then_body,
            Address::Bool(false) => self.else_body,
            _ => {
                let what = "a `conditional` on a run-time condition";
                return Err(StimError::Unsupported(what.into()));
            }
        };
        emitter.block(arm)
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for Repeat {
    fn interpret(&self, _emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        let what = "a `repeat` loop, because Stim cannot end a loop on a measurement";
        Err(StimError::Unsupported(what.into()))
    }
}

impl<'a> Interpretable<StimEmitter<'a>, EmitStim> for For<SquinType> {
    fn interpret(&self, _emitter: &mut StimEmitter<'a>) -> Result<(), StimError> {
        Err(StimError::Unsupported(
            "a `for` loop. Unroll the loop first".into(),
        ))
    }
}

nothing!(Yield<SquinType>);
