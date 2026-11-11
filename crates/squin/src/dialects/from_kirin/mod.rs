//! Adapt the Kirin statements that the Squin language includes.

mod arithmetic;
mod comparison;
mod conditional;
mod constant;
mod function;
mod loops;

use kirin_scf::{StructuredControlFlow, Yield};

use crate::ir::traits::macros::{delegate, plain};
use crate::ir::traits::{Execute, Structure, Threads, Typed};
use crate::ir::types::SquinType;

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

plain!(Threads, for Yield<SquinType>);
plain!(Typed, for Yield<SquinType>);
plain!(Structure, for Yield<SquinType>);
plain!(Execute, for Yield<SquinType>);
