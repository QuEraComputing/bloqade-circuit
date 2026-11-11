//! Define the Squin rules for Kirin constants.

use kirin_constant::Constant;

use kirin::prelude::*;

use crate::ir::contexts::Failure;
use crate::ir::contexts::{Evaluator, TypeCheck};
use crate::ir::traits::macros::plain;
use crate::ir::traits::{Execute, Offset, Structure, Threads, Typed};
use crate::ir::types::{Scalar, SquinType};

plain!(Threads, for Constant<Scalar, SquinType>);

impl Typed for Constant<Scalar, SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
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
    fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
        machine.write(self.result, self.value.into());
        Ok(())
    }
}
