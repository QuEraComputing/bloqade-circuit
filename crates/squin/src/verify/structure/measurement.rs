//! Describe the structure of the measurement statements.

use super::{Lending, Nesting, Offset, Place, Structure};
use crate::ir::dialects::measurement::{
    GetResult, IsLost, IsOne, IsZero, MeasurementOp, PackResults, ResultsLength,
};

delegate!(MeasurementOp {
    Pack,
    Get,
    Length,
    IsZero,
    IsOne,
    IsLost
});
placed!(Anywhere, for PackResults, GetResult, ResultsLength, IsZero, IsOne, IsLost);
