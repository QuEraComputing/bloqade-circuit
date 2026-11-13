//! Define the qubit dialect: the statements on single qubits.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;
use kirin_interpreter::Interpretable;
use smallvec::smallvec;

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Pairs, Threads};
use crate::ir::types::SquinType;

/// Allocate one qubit in the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$alloc")]
pub struct Alloc {
    #[kirin(type = SquinType::Wire)]
    pub wire: ResultValue,
}

/// End the life of the qubit of `wire`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$free {wire}")]
pub struct Free {
    pub wire: SSAValue,
}

/// Measure the qubit of `wire` and keep the qubit.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$measure {wire}")]
pub struct Measure {
    pub wire: SSAValue,
    #[kirin(type = SquinType::Wire)]
    pub wire_out: ResultValue,
    #[kirin(type = SquinType::MeasurementResult)]
    pub result: ResultValue,
}

/// Reset the qubit of `wire` to the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$reset {wire}")]
pub struct Reset {
    pub wire: SSAValue,
    #[kirin(type = SquinType::Wire)]
    pub wire_out: ResultValue,
}

/// Hold one statement of the qubit dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint, Interpretable)]
#[wraps]
#[kirin(builders, type = SquinType)]
pub enum QubitOp {
    Alloc(Alloc),
    Free(Free),
    Measure(Measure),
    Reset(Reset),
}

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

plain!(Threads, for Alloc, Free);

impl Threads for Measure {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

impl Threads for Reset {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}
