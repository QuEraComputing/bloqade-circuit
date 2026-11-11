//! Define the Squin rules for Kirin comparisons.

use kirin_cmp::Cmp;
use std::cmp::Ordering;

use kirin::prelude::*;

use crate::dialect::macros::plain;
use crate::dialect::semantics::{Failure, Value};
use crate::dialect::traits::{Evaluator, Execute, Structure, Threads, TypeCheck, Typed};
use crate::dialect::types::SquinType;

plain!(Threads, for Cmp<SquinType>);
plain!(Structure, for Cmp<SquinType>);

/// Decide a comparison from the order of its two operands.
///
/// Two floats have no order if one of them is not a number.
type Test = fn(Option<Ordering>) -> bool;

/// Return the operands, the result and the test of a comparison.
fn comparison(cmp: &Cmp<SquinType>) -> Option<(SSAValue, SSAValue, ResultValue, Test)> {
    use Ordering::{Equal, Greater, Less};
    Some(match *cmp {
        Cmp::Eq { lhs, rhs, result } => (lhs, rhs, result, |order| order == Some(Equal)),
        Cmp::Ne { lhs, rhs, result } => (lhs, rhs, result, |order| order != Some(Equal)),
        Cmp::Lt { lhs, rhs, result } => (lhs, rhs, result, |order| order == Some(Less)),
        Cmp::Le { lhs, rhs, result } => (lhs, rhs, result, |order| {
            matches!(order, Some(Less | Equal))
        }),
        Cmp::Gt { lhs, rhs, result } => (lhs, rhs, result, |order| order == Some(Greater)),
        Cmp::Ge { lhs, rhs, result } => (lhs, rhs, result, |order| {
            matches!(order, Some(Greater | Equal))
        }),
        _ => return None,
    })
}

/// Check that a comparison reads two values of one type and gives a `Bool`.
impl Typed for Cmp<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let Some((lhs, rhs, result, _)) = comparison(self) else {
            return;
        };
        let ty = typing.ty(lhs);
        if ty.is_number() || ty == SquinType::Bool {
            typing.exact(rhs, ty);
        } else {
            typing.fail(lhs, "Int, Float or Bool");
        }
        typing.expect(result, SquinType::Bool);
    }
}

impl Execute for Cmp<SquinType> {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let Some((lhs, rhs, result, accepts)) = comparison(self) else {
            return Ok(());
        };
        let order = match (machine.read(lhs)?, machine.read(rhs)?) {
            (Value::Int(left), Value::Int(right)) => Some(left.cmp(&right)),
            (Value::Float(left), Value::Float(right)) => left.partial_cmp(&right),
            (Value::Bool(left), Value::Bool(right)) => Some(left.cmp(&right)),
            (other, _) => return Err(other.is_not("two values of one kind")),
        };
        machine.write(result, Value::Bool(accepts(order)));
        Ok(())
    }
}
