//! Define the Squin rules for Kirin functions and returns.

use kirin::prelude::*;
use kirin_function::{Function, Return};

use crate::ir::contexts::TypeCheck;
use crate::ir::traits::macros::plain;
use crate::ir::traits::{Execute, Structure, Threads, Typed};
use crate::ir::types::SquinType;

plain!(Threads, for Function<SquinType>, Return<SquinType>);
plain!(Typed, for Return<SquinType>);
plain!(Structure, for Function<SquinType>, Return<SquinType>);
plain!(Execute, for Function<SquinType>, Return<SquinType>);

impl Typed for Function<SquinType> {
    fn check<C: TypeCheck>(&self, typing: &mut C) {
        let signature = self.signature().unwrap();
        for body in self.cfgs() {
            typing.function(*body, &signature);
        }
    }
}
