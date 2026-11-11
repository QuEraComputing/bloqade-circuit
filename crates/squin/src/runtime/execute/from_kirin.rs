//! Run the Kirin statements that `Squin` includes.

use std::cmp::Ordering;

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use super::Execute;
use crate::ir::macros::plain;
use crate::ir::types::{Scalar, SquinType};
use crate::runtime::number::{self, Binary};
use crate::runtime::{Evaluator, Failure, Value};

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

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

impl Execute for Constant<Scalar, SquinType> {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        machine.write(self.result, self.value.clone().into());
        Ok(())
    }
}

impl Execute for Arith<SquinType> {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let (lhs, rhs, result, operation) = match *self {
            Arith::Add { lhs, rhs, result } => (lhs, rhs, result, Binary::Add),
            Arith::Sub { lhs, rhs, result } => (lhs, rhs, result, Binary::Sub),
            Arith::Mul { lhs, rhs, result } => (lhs, rhs, result, Binary::Mul),
            Arith::Div { lhs, rhs, result } => (lhs, rhs, result, Binary::Div),
            Arith::Rem { lhs, rhs, result } => (lhs, rhs, result, Binary::Rem),
            Arith::Neg { operand, result } => {
                let value = match machine.read(operand)? {
                    Value::Number(value) => number::negate(value)?,
                    other => return Err(other.is_not("a number")),
                };
                machine.write(result, Value::Number(value));
                return Ok(());
            }
            _ => return Ok(()),
        };
        let value = match (machine.read(lhs)?, machine.read(rhs)?) {
            (Value::Number(left), Value::Number(right)) => {
                Value::Number(number::binary(operation, left, right)?)
            }
            (other, _) => return Err(other.is_not("two numbers of the same type")),
        };
        machine.write(result, value);
        Ok(())
    }
}

impl Execute for Cmp<SquinType> {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let Some((lhs, rhs, result, accepts)) = comparison(self) else {
            return Ok(());
        };
        let order = match (machine.read(lhs)?, machine.read(rhs)?) {
            (Value::Number(left), Value::Number(right)) => number::compare(left, right)?,
            (Value::Bool(left), Value::Bool(right)) => Some(left.cmp(&right)),
            (other, _) => return Err(other.is_not("two values of one kind")),
        };
        machine.write(result, Value::Bool(accepts(order)));
        Ok(())
    }
}

/// Run the arm that the condition selects and bind what the arm yields.
impl Execute for If<SquinType> {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let arm = match machine.read(self.condition())? {
            Value::Bool(true) => self.then_block(),
            Value::Bool(false) => self.else_block(),
            other => return Err(other.is_not("a truth value")),
        };
        let yielded = machine.block(arm, Vec::new())?;
        machine.bind(self.results(), yielded)
    }
}

/// Run the loop body once for each index and pass the carried values along.
impl Execute for For<SquinType> {
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        let (start, end) = (machine.int(self.start())?, machine.int(self.end())?);
        let step = machine.int(self.step())?;
        let stride = usize::try_from(step).ok().filter(|stride| *stride > 0);
        let stride = stride.ok_or(Failure::Step(step))?;
        let carried = self.init_args().iter().map(|value| machine.read(*value));
        let mut carried = carried.collect::<Result<Vec<_>, _>>()?;
        for index in (start..end).step_by(stride) {
            carried.insert(0, Value::from(index));
            carried = machine.block(self.body(), carried)?;
        }
        machine.bind(self.results(), carried)
    }
}

plain!(Execute, for Function<SquinType>, Return<SquinType>);

plain!(Execute, for Yield<SquinType>);
