//! Give the Kirin constant, arithmetic and comparison statements their squin rules.

use std::cmp::Ordering;

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;

use crate::macros::plain;
use crate::run::{Backend, Execute, Failure, Machine, Value};
use crate::threads::Threads;
use crate::types::{Scalar, SquinType};
use crate::verify::{Offset, Structure, Typed, Typing};

plain!(Threads, for Constant<Scalar, SquinType>, Arith<SquinType>, Cmp<SquinType>);
plain!(Structure, for Cmp<SquinType>);

impl Typed for Constant<Scalar, SquinType> {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        typing.exact(self.result, self.value.type_of());
    }
}

impl Structure for Constant<Scalar, SquinType> {
    fn offset(&self) -> Option<Offset> {
        match self.value {
            Scalar::Int(value) => Some(Offset::Constant(value)),
            _ => None,
        }
    }
}

impl Execute for Constant<Scalar, SquinType> {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        machine.write(self.result, self.value.into());
        Ok(())
    }
}

/// Check that the operands and the result are numbers of one type.
impl Typed for Arith<SquinType> {
    fn check(&self, typing: &mut Typing<'_, '_>) {
        let (operands, result) = match *self {
            Arith::Add { lhs, rhs, result }
            | Arith::Sub { lhs, rhs, result }
            | Arith::Mul { lhs, rhs, result }
            | Arith::Div { lhs, rhs, result }
            | Arith::Rem { lhs, rhs, result } => (vec![lhs, rhs], result),
            Arith::Neg { operand, result } => (vec![operand], result),
            _ => return,
        };
        let ty = typing.ty(result);
        if ty.is_number() {
            typing.each(operands, ty);
        } else {
            typing.fail(result.into(), "Int or Float");
        }
    }
}

impl Structure for Arith<SquinType> {
    fn offset(&self) -> Option<Offset> {
        match *self {
            Arith::Add { lhs, rhs, .. } => Some(Offset::Sum(lhs, rhs)),
            Arith::Sub { lhs, rhs, .. } => Some(Offset::Difference(lhs, rhs)),
            _ => None,
        }
    }
}

impl Execute for Arith<SquinType> {
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
        type Whole = fn(i64, i64) -> Option<i64>;
        type Real = fn(f64, f64) -> f64;
        let (lhs, rhs, result, whole, real): (_, _, _, Whole, Real) = match *self {
            Arith::Add { lhs, rhs, result } => (lhs, rhs, result, i64::checked_add, |a, b| a + b),
            Arith::Sub { lhs, rhs, result } => (lhs, rhs, result, i64::checked_sub, |a, b| a - b),
            Arith::Mul { lhs, rhs, result } => (lhs, rhs, result, i64::checked_mul, |a, b| a * b),
            Arith::Div { lhs, rhs, result } => (lhs, rhs, result, i64::checked_div, |a, b| a / b),
            Arith::Rem { lhs, rhs, result } => (lhs, rhs, result, i64::checked_rem, |a, b| a % b),
            Arith::Neg { operand, result } => {
                let negated = match machine.read(operand)? {
                    Value::Int(value) => {
                        Value::Int(value.checked_neg().ok_or(Failure::Arithmetic)?)
                    }
                    Value::Float(value) => Value::Float(-value),
                    other => return Err(other.is_not("a number")),
                };
                machine.write(result, negated);
                return Ok(());
            }
            _ => return Ok(()),
        };
        let value = match (machine.read(lhs)?, machine.read(rhs)?) {
            (Value::Int(left), Value::Int(right)) => {
                Value::Int(whole(left, right).ok_or(Failure::Arithmetic)?)
            }
            (Value::Float(left), Value::Float(right)) => Value::Float(real(left, right)),
            (other, _) => return Err(other.is_not("two numbers of one kind")),
        };
        machine.write(result, value);
        Ok(())
    }
}

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
    fn check(&self, typing: &mut Typing<'_, '_>) {
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
    fn execute<B: Backend>(&self, machine: &mut Machine<'_, B>) -> Result<(), Failure> {
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
