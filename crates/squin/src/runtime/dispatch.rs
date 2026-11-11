//! Select the function body that accepts the arguments of a call.

use kirin::prelude::*;

use super::Value;
use crate::ir::Squin;
use crate::ir::types::SquinType;

/// Tell why no single specialization accepts the arguments.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mismatch {
    /// No specialization accepts the argument types.
    NoMatch,
    /// More than one specialization accepts them, and none is the most specific.
    Ambiguous,
}

/// Return the most specific specialization of `candidates` that accepts `arguments`.
///
/// A specialization supplies a function body for one parameter type signature.
/// A function with one specialization uses it for every call.
pub fn select<'a, M>(
    candidates: &'a [SpecializedFunctionInfo<Squin>],
    arguments: &[Value<M>],
) -> Result<&'a SpecializedFunctionInfo<Squin>, Mismatch> {
    if let [only] = candidates {
        return Ok(only);
    }
    let accepts = |candidate: &&SpecializedFunctionInfo<Squin>| {
        let parameters = candidate.signature().params();
        parameters.len() == arguments.len()
            && arguments
                .iter()
                .zip(parameters)
                .all(|(value, ty)| value.matches_type(*ty))
    };
    let matching: Vec<_> = candidates.iter().filter(accepts).collect();
    let most_specific = |candidate: &&&SpecializedFunctionInfo<Squin>| {
        let parameters = candidate.signature().params();
        !matching
            .iter()
            .any(|other| narrower(other.signature().params(), parameters))
    };
    let best: Vec<_> = matching.iter().filter(most_specific).collect();
    match best.as_slice() {
        [specialization] => Ok(specialization),
        [] => Err(Mismatch::NoMatch),
        _ => Err(Mismatch::Ambiguous),
    }
}

/// Check whether the signature `left` accepts fewer argument types than `right`.
fn narrower(left: &[SquinType], right: &[SquinType]) -> bool {
    let fits = left
        .iter()
        .zip(right)
        .all(|(left, right)| left.is_subseteq(right));
    left.len() == right.len() && fits && left != right
}
