//! Define the repeat loop: run a body until it reports success.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::ir::traits::Threads;
use crate::ir::types::SquinType;

/// Run `body` until it yields a true stop flag, as a repeat-until-success loop does.
///
/// The first run receives `inputs` as its block arguments. The body yields a
/// stop flag, a `Bool`, and then one value for each input.
/// If the flag is false, the body runs again on those values. If it is true,
/// they become `results`. Linear values enter the body only through `inputs`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$repeat ({inputs}) do {body}[ -> {results:type}]")]
pub struct Repeat {
    pub inputs: Vec<SSAValue>,
    pub body: Block,
    pub results: Vec<ResultValue>,
}

// The verifier follows the carried values through `Nesting::Loop`, as it does
// for a Kirin `for`.
impl Threads for Repeat {}
