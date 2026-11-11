//! Implement the squin statement traits for the Kirin statements that `Squin` includes.

use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use crate::ir::macros::{delegate, plain};
use crate::ir::traits::{Nesting, Offset, Structure, Threads};
use crate::ir::types::{Scalar, SquinType};

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

plain!(Threads, for Constant<Scalar, SquinType>);

plain!(Threads, for Arith<SquinType>);

plain!(Threads, for Cmp<SquinType>);

plain!(Threads, for If<SquinType>);

plain!(Threads, for For<SquinType>);

plain!(Threads, for Function<SquinType>, Return<SquinType>);

plain!(Threads, for Yield<SquinType>);

impl Structure for Constant<Scalar, SquinType> {
    fn offset(&self) -> Option<Offset> {
        match self.value {
            Scalar::Int(value) => Some(Offset::Constant(value)),
            _ => None,
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

plain!(Structure, for Cmp<SquinType>);

impl Structure for If<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Arms([self.then_block(), self.else_block()])
    }
}

impl Structure for For<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Loop {
            body: self.body(),
            initial: self.init_args(),
        }
    }
}

plain!(Structure, for Function<SquinType>, Return<SquinType>);

plain!(Structure, for Yield<SquinType>);
