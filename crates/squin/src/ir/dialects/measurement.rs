//! Define the measurement dialect: the statements on measurement results.
//!
//! A measurement of a neutral atom ends in one of three ways: the qubit is
//! zero, the qubit is one, or the atom is lost. A `MeasurementResult` holds
//! that outcome, and `is_zero`, `is_one` and `is_lost` read it as a `Bool`.
//! A result is immutable, so every statement here is pure.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use crate::ir::macros::{delegate, plain};
use kirin::prelude::*;
use kirin_arith::ArithType;
use kirin_interpreter::Interpretable;

use crate::ir::traits::Threads;
use crate::ir::types::{Length, SquinType};

/// Form a `MeasurementResults` value that holds `results` in operand order.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$pack_results {results} -> {packed:type}")]
pub struct PackResults {
    pub results: Vec<SSAValue>,
    #[kirin(type = SquinType::MeasurementResults(Length::Known(results.len() as u64)))]
    pub packed: ResultValue,
}

/// Return the measurement result at `index` of `results`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$get_result {results}, {index}")]
pub struct GetResult {
    pub results: SSAValue,
    pub index: SSAValue,
    #[kirin(type = SquinType::MeasurementResult)]
    pub result: ResultValue,
}

/// Return the number of measurement results that `results` holds.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$results_length {results}")]
pub struct ResultsLength {
    pub results: SSAValue,
    #[kirin(type = SquinType::Number(ArithType::I64))]
    pub length: ResultValue,
}

/// Tell whether `result` found the qubit in the zero state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$is_zero {result}")]
pub struct IsZero {
    pub result: SSAValue,
    #[kirin(type = SquinType::Bool)]
    pub answer: ResultValue,
}

/// Tell whether `result` found the qubit in the one state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$is_one {result}")]
pub struct IsOne {
    pub result: SSAValue,
    #[kirin(type = SquinType::Bool)]
    pub answer: ResultValue,
}

/// Tell whether the atom was lost before `result` could find a state.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(pure, builders, type = SquinType)]
#[chumsky(format = "$is_lost {result}")]
pub struct IsLost {
    pub result: SSAValue,
    #[kirin(type = SquinType::Bool)]
    pub answer: ResultValue,
}

/// Hold one statement of the measurement dialect.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint, Interpretable)]
#[wraps]
#[kirin(pure, builders, type = SquinType)]
pub enum MeasurementOp {
    Pack(PackResults),
    Get(GetResult),
    Length(ResultsLength),
    IsZero(IsZero),
    IsOne(IsOne),
    IsLost(IsLost),
}

delegate!(MeasurementOp {
    Pack,
    Get,
    Length,
    IsZero,
    IsOne,
    IsLost
});

plain!(Threads, for PackResults, GetResult, ResultsLength, IsZero, IsOne, IsLost);
