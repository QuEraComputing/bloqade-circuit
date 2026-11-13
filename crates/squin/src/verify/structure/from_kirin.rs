//! Describe the blocks and integer expressions of the Kirin statements.

use kirin_arith::Arith;
use kirin_arith::ArithValue;
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use super::{Lending, Nesting, Offset, Place, Structure};
use crate::ir::macros::plain;
use crate::ir::types::{Scalar, SquinType};

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });
placed!(Anywhere, for Cmp<SquinType>, Bitwise<SquinType>);
plain!(Structure, for Function<SquinType>, Return<SquinType>);
plain!(Structure, for Yield<SquinType>);

impl Structure for Constant<Scalar, SquinType> {
    fn place(&self) -> Place {
        Place::Anywhere
    }

    fn offset(&self) -> Option<Offset> {
        match self.value {
            Scalar::Number(ArithValue::I64(value)) => Some(Offset::Constant(value)),
            _ => None,
        }
    }
}

impl Structure for Arith<SquinType> {
    fn place(&self) -> Place {
        Place::Anywhere
    }

    fn offset(&self) -> Option<Offset> {
        match *self {
            Arith::Add { lhs, rhs, .. } => Some(Offset::Sum(lhs, rhs)),
            Arith::Sub { lhs, rhs, .. } => Some(Offset::Difference(lhs, rhs)),
            _ => None,
        }
    }
}

impl Structure for If<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Arms {
            arms: [self.then_block(), self.else_block()],
            inputs: &[],
        }
    }
}

impl Structure for For<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Loop {
            body: self.body(),
            initial: self.init_args(),
            leading_arguments: 1,
            leading_yields: 0,
        }
    }
}
