//! Describe which register statements borrow or return an element.

use super::{Lending, Nesting, Offset, Structure};
use crate::ir::macros::plain;
use crate::ir::ops::{
    AllocRegister, Borrow, FreeRegister, Join, LengthOf, MeasureRegister, Pack, RegisterOp,
    Release, Replace, Split,
};

delegate!(RegisterOp {
    AllocRegister,
    FreeRegister,
    Pack,
    Split,
    Join,
    LengthOf,
    MeasureRegister,
    Borrow,
    Release,
    Replace,
});

plain!(Structure, for AllocRegister, FreeRegister, Pack, Split, Join, LengthOf, MeasureRegister, Replace);

impl Structure for Borrow {
    fn lending(&self) -> Option<Lending> {
        Some(Lending::Borrow {
            register: self.register,
            index: self.index,
            register_out: self.register_out,
            slot: self.slot,
            wire: self.wire,
        })
    }
}

impl Structure for Release {
    fn lending(&self) -> Option<Lending> {
        Some(Lending::Release {
            register: self.register,
            slot: self.slot,
            wire: self.wire,
        })
    }
}
