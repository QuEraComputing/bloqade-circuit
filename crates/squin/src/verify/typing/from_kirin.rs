//! Check the types of the Kirin statements that `Squin` includes.

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_arith::ArithType;
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use super::{TypeCheck, Typed};
use crate::ir::macros::plain;
use crate::ir::types::{Scalar, SquinType};

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

impl Typed for Constant<Scalar, SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.exact(self.result, self.value.type_of());
    }
}

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
            typing.fail(result, "a numeric type");
        }
    }
}

/// Check that a bitwise statement reads and gives values of one type.
///
/// `and`, `or`, `xor` and `not` work on a `Bool` or an `Int`, so they combine
/// the answers of `is_zero`, `is_one` and `is_lost`. `shl` and `shr` work on
/// an `Int` only.
impl Typed for Bitwise<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let integer = SquinType::Number(ArithType::I64);
        let (operands, result, logical) = match *self {
            Bitwise::And {
                lhs, rhs, result, ..
            }
            | Bitwise::Or {
                lhs, rhs, result, ..
            }
            | Bitwise::Xor {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, true),
            Bitwise::Not {
                operand, result, ..
            } => (vec![operand], result, true),
            Bitwise::Shl {
                lhs, rhs, result, ..
            }
            | Bitwise::Shr {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, false),
            _ => return,
        };
        let ty = typing.ty(result.into());
        if ty == integer || (logical && ty == SquinType::Bool) {
            typing.each(operands, ty);
        } else if logical {
            typing.fail(result, "Bool or Int");
        } else {
            typing.fail(result, "Int");
        }
    }
}

/// Check that a comparison reads two values of one type and gives a `Bool`.
impl Typed for Cmp<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let (lhs, rhs, result) = match *self {
            Cmp::Eq { lhs, rhs, result }
            | Cmp::Ne { lhs, rhs, result }
            | Cmp::Lt { lhs, rhs, result }
            | Cmp::Le { lhs, rhs, result }
            | Cmp::Gt { lhs, rhs, result }
            | Cmp::Ge { lhs, rhs, result } => (lhs, rhs, result),
            _ => return,
        };
        let ty = typing.ty(lhs);
        if ty.is_number() || ty == SquinType::Bool {
            typing.exact(rhs, ty);
        } else {
            typing.fail(lhs, "a numeric type or Bool");
        }
        typing.expect(result, SquinType::Bool);
    }
}

/// Check that each arm yields the types of the results.
impl Typed for If<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.expect(self.condition(), SquinType::Bool);
        for arm in [self.then_block(), self.else_block()] {
            typing.arity(0, typing.arguments(arm).len());
            typing.flows(&typing.yields(arm), self.results());
        }
    }
}

/// Check that the loop body receives and yields the types that it carries.
impl Typed for For<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        typing.each(
            [self.induction_var(), self.start(), self.end(), self.step()],
            SquinType::Number(ArithType::I64),
        );
        let arguments = typing.arguments(self.body());
        if !typing.arity(self.init_args().len() + 1, arguments.len()) {
            return;
        }
        let (index, carried) = arguments.split_first().unwrap();
        typing.exact(*index, SquinType::Number(ArithType::I64));
        typing.flows(self.init_args(), carried);
        typing.flows(&typing.yields(self.body()), carried);
        typing.flows(carried, self.results());
    }
}

plain!(Typed, for Return<SquinType>);

impl Typed for Function<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let signature = self.signature().unwrap();
        for body in self.cfgs() {
            typing.function(*body, &signature);
        }
    }
}

plain!(Typed, for Yield<SquinType>);
