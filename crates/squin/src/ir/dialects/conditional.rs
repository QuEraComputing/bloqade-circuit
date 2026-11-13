//! Define the conditional: a two-way branch that hands its wires to the arm that runs.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::ir::traits::Threads;
use crate::ir::types::SquinType;

/// Run `then_body` if `condition` holds and `else_body` if it does not.
///
/// Each arm receives `inputs` as its block arguments and ends with `yield`,
/// and the yields of the arm that runs become `results`. Linear values cross
/// into an arm only through `inputs`. An arm can still read classical values
/// of outer blocks.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(
    format = "$conditional {condition} ({inputs}) then {then_body} else {else_body}[ -> {results:type}]"
)]
pub struct Conditional {
    pub condition: SSAValue,
    pub inputs: Vec<SSAValue>,
    pub then_body: Block,
    pub else_body: Block,
    pub results: Vec<ResultValue>,
}

// The arms can allocate, free and measure qubits, so result `i` does not
// always continue input `i`.
impl Threads for Conditional {}
