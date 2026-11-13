//! Check the types of the measurement statements.

use super::{TypeCheck, Typed};
use crate::ir::dialects::measurement::{
    GetResult, IsLost, IsOne, IsZero, MeasurementOp, PackResults, ResultsLength,
};
use crate::ir::types::{Length, SquinType};
use kirin_arith::ArithType;

delegate!(MeasurementOp {
    Pack,
    Get,
    Length,
    IsZero,
    IsOne,
    IsLost
});

impl Typed for PackResults {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(self.results.iter().copied(), SquinType::MeasurementResult);
        let length = Length::Known(self.results.len() as u64);
        typing.covers(self.packed, SquinType::MeasurementResults(length));
    }
}

impl Typed for GetResult {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.results, SquinType::MeasurementResults(Length::Any));
        typing.expect(self.index, SquinType::Number(ArithType::I64));
        typing.expect(self.result, SquinType::MeasurementResult);
    }
}

impl Typed for ResultsLength {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.results, SquinType::MeasurementResults(Length::Any));
        typing.expect(self.length, SquinType::Number(ArithType::I64));
    }
}

/// Check that a read of a result takes a `MeasurementResult` and gives a `Bool`.
macro_rules! reads {
    ($($statement:ty),+) => {$(
        impl Typed for $statement {
            fn check<C: TypeCheck>(&self, typing: &mut C) {
                typing.expect(self.result, SquinType::MeasurementResult);
                typing.expect(self.answer, SquinType::Bool);
            }
        }
    )+};
}

reads!(IsZero, IsOne, IsLost);
