//! Check the types of the qubit statements.

use super::{TypeCheck, Typed};
use crate::ir::dialects::qubit::{Alloc, Free, Measure, QubitOp, Reset};
use crate::ir::types::SquinType;

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

impl Typed for Alloc {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.wire, SquinType::Wire);
    }
}

impl Typed for Free {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.wire, SquinType::Wire);
    }
}

impl Typed for Measure {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.wire, SquinType::Wire);
        typing.expect(self.wire_out, SquinType::Wire);
        typing.expect(self.result, SquinType::MeasurementResult);
    }
}

impl Typed for Reset {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.wire, SquinType::Wire);
        typing.expect(self.wire_out, SquinType::Wire);
    }
}
