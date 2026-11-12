//! Check the types of the bits statements.

use super::{TypeCheck, Typed};
use crate::ir::dialects::bits::{BitsGet, BitsLength, BitsOp, BitsPack};
use crate::ir::types::{Length, SquinType};
use kirin_arith::ArithType;

delegate!(BitsOp { Pack, Get, Length });

impl Typed for BitsPack {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(self.bits.iter().copied(), SquinType::Bit);
        let length = Length::Known(self.bits.len() as u64);
        typing.covers(self.result, SquinType::Bits(length));
    }
}

impl Typed for BitsGet {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.bits, SquinType::Bits(Length::Any));
        typing.expect(self.index, SquinType::Number(ArithType::I64));
        typing.expect(self.bit, SquinType::Bit);
    }
}

impl Typed for BitsLength {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.bits, SquinType::Bits(Length::Any));
        typing.expect(self.length, SquinType::Number(ArithType::I64));
    }
}
