//! Define the circuit dialect: a region of quantum dataflow.

// The builders that `derive(Dialect)` generates write `field: field`, and clippy
// reports that code at the fields of this file.
#![allow(clippy::redundant_field_names)]

use kirin::prelude::*;

use crate::ir::traits::Threads;
use crate::ir::types::SquinType;

/// Run the dataflow graph `body` on `inputs` and return its yields as `results`.
///
/// The graph is isolated: it reads only its own ports, so every wire enters
/// through `inputs` and leaves through `yield`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
#[chumsky(format = "$circuit {inputs} {body}[ -> {results:type}]")]
pub struct Circuit {
    pub inputs: Vec<SSAValue>,
    pub body: DiGraph,
    pub results: Vec<ResultValue>,
}

// A region can allocate, free and measure qubits, so its results do not
// continue its inputs one by one.
impl Threads for Circuit {}

impl Circuit {
    /// Build a region on `inputs` that runs `body`, with one result of each type in `types`.
    ///
    /// The generated `Circuit::new` gives each result the type `Any`, because
    /// the derive cannot compute the type of a graph yield. This constructor
    /// sets each result type afterwards. The result is the new statement with
    /// its results.
    pub fn build(
        builder: &mut BuilderStageInfo<crate::ir::Squin>,
        inputs: Vec<SSAValue>,
        body: DiGraph,
        types: &[SquinType],
    ) -> (Statement, Vec<ResultValue>) {
        let built = Circuit::new(builder, types.len(), inputs, body);
        for (result, ty) in built.results.iter().zip(types) {
            builder.ssa_arena_mut()[SSAValue::from(*result)].set_ty(*ty);
        }
        (built.id, built.results)
    }
}
