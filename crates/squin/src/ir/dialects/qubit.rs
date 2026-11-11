//! Define the qubit dialect: the statements on single qubits.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use std::marker::PhantomData;

use kirin::prelude::*;
use smallvec::smallvec;

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Pairs, Threads};

use crate::ir::types::QuantumTypes;

/// Allocate one qubit in the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$alloc")]
pub struct Alloc<Ty: QuantumTypes> {
    #[kirin(type = Ty::wire())]
    pub wire: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// End the life of the qubit of `wire`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$free {wire}")]
pub struct Free<Ty: QuantumTypes> {
    pub wire: SSAValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Measure the qubit of `wire` and keep the qubit.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$measure {wire}")]
pub struct Measure<Ty: QuantumTypes> {
    pub wire: SSAValue,
    #[kirin(type = Ty::wire())]
    pub wire_out: ResultValue,
    #[kirin(type = Ty::bit())]
    pub bit: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Reset the qubit of `wire` to the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Ty)]
#[chumsky(format = "$reset {wire}")]
pub struct Reset<Ty: QuantumTypes> {
    pub wire: SSAValue,
    #[kirin(type = Ty::wire())]
    pub wire_out: ResultValue,
    #[kirin(default)]
    pub marker: PhantomData<Ty>,
}

/// Hold one statement of the qubit dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[wraps]
#[kirin(builders, type = Ty)]
pub enum QubitOp<Ty: QuantumTypes> {
    Alloc(Alloc<Ty>),
    Free(Free<Ty>),
    Measure(Measure<Ty>),
    Reset(Reset<Ty>),
}

delegate!(generic QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

plain!(generic Threads, for Alloc, Free);

impl<Ty: QuantumTypes> Threads for Measure<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}

impl<Ty: QuantumTypes> Threads for Reset<Ty> {
    fn threads(&self) -> Pairs {
        smallvec![(self.wire, self.wire_out)]
    }
}
