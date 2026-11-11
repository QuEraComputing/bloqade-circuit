//! Define the qubit dialect: the statements on single qubits.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;
use smallvec::smallvec;

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Pairs, Structure, Threads};
use crate::ir::types::SquinType;

/// Allocate one qubit in the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$alloc -> {wire:type}")]
pub struct Alloc {
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
#[chumsky(format = "$measure {wire} -> {wire_out:type}, {bit:type}")]
pub struct Measure {
    pub wire: SSAValue,
    pub wire_out: ResultValue,
    pub bit: ResultValue,
}

/// Reset the qubit of `wire` to the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$reset {wire} -> {wire_out:type}")]
pub struct Reset {
    pub wire: SSAValue,
    pub wire_out: ResultValue,
}

/// Hold one statement of the qubit dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
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

plain!(Structure, for Alloc, Free, Measure, Reset);
