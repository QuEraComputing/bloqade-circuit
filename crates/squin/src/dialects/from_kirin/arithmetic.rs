//! Define the Squin rules for Kirin arithmetic.

use kirin_arith::Arith;

use crate::ir::contexts::{Evaluator, TypeCheck};
use crate::ir::contexts::{Failure, Value};
use crate::ir::traits::macros::plain;
use crate::ir::traits::{Execute, Offset, Structure, Threads, Typed};
use crate::ir::types::SquinType;

plain!(Threads, for Arith<SquinType>);

/// Check that the operands and the result are numbers of one type.
impl Typed for Arith<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let (operands, result) = match *self {
            Arith::Add { lhs, rhs, result }
            | Arith::Sub { lhs, rhs, result }
            | Arith::Mul { lhs, rhs, result }
            | Arith::Div { lhs, rhs, result }
            | Arith::Rem { lhs, rhs, result } => (vec![lhs, rhs], result),
            Arith::Neg { operand, result } => (vec![operand], result),
            _ => return,
        };
        let ty = typing.ty(result.into());
        if ty.is_number() {
            typing.each(operands, ty);
        } else {
            typing.fail(result, "Int or Float");
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
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
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
