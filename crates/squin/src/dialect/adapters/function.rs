//! Define the Squin rules for Kirin functions and returns.

use kirin::prelude::*;
use kirin_function::{Function, Return};

use crate::dialect::macros::plain;
use crate::dialect::traits::{Execute, Structure, Threads, TypeCheck, Typed};
use crate::dialect::types::SquinType;

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
