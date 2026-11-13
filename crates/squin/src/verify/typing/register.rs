//! Check the types of the register statements.

use super::{TypeCheck, Typed};
use crate::ir::dialects::register::{
    AllocRegister, Borrow, FreeRegister, Join, LengthOf, MeasureRegister, Pack, RegisterOp,
    Release, Replace, Split,
};
use crate::ir::types::{Length, SquinType};
use kirin_arith::ArithType;

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

impl Typed for AllocRegister {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.size, SquinType::Number(ArithType::I64));
        typing.whole(self.register);
    }
}

impl Typed for FreeRegister {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
    }
}

impl Typed for Pack {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(self.wires.iter().copied(), SquinType::Wire);
        let length = Length::Known(self.wires.len() as u64);
        typing.covers(self.register, SquinType::register(length));
    }
}

impl Typed for Split {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
        typing.expect(self.index, SquinType::Number(ArithType::I64));
        typing.whole(self.before);
        typing.whole(self.after);
    }
}

impl Typed for Join {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.first);
        typing.whole(self.second);
        typing.whole(self.register);
    }
}

impl Typed for LengthOf {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.register(self.register);
        typing.exact(self.register_out, typing.ty(self.register));
        typing.expect(self.length, SquinType::Number(ArithType::I64));
    }
}

impl Typed for MeasureRegister {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
        typing.exact(self.register_out, typing.ty(self.register));
        if let Some((len, _)) = typing.register(self.register) {
            typing.exact(self.results, SquinType::MeasurementResults(len));
        }
    }
}

impl Typed for Borrow {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.index, SquinType::Number(ArithType::I64));
        typing.expect(self.slot, SquinType::Slot);
        typing.expect(self.wire, SquinType::Wire);
        if let Some((len, lent)) = typing.register(self.register) {
            let Some(lent) = lent.checked_add(1) else {
                typing.fail(
                    self.register,
                    "a register with fewer than 4294967295 open borrows",
                );
                return;
            };
            typing.exact(self.register_out, SquinType::Register { len, lent });
        }
    }
}

impl Typed for Release {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.slot, SquinType::Slot);
        typing.expect(self.wire, SquinType::Wire);
        match typing.register(self.register) {
            Some((_, 0)) => typing.fail(self.register, "a register with an empty element"),
            Some((len, lent)) => {
                let lent = lent - 1;
                typing.exact(self.register_out, SquinType::Register { len, lent });
            }
            None => {}
        }
    }
}

impl Typed for Replace {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.whole(self.register);
        typing.expect(self.index, SquinType::Number(ArithType::I64));
        typing.expect(self.wire, SquinType::Wire);
        typing.exact(self.register_out, typing.ty(self.register));
        typing.expect(self.wire_out, SquinType::Wire);
    }
}
