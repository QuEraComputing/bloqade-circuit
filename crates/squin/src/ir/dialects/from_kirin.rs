//! Implement the squin statement traits for the Kirin statements that `Squin` includes.

use kirin_arith::Arith;
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;

use kirin_constant::Constant;
use kirin_function::{Function, Return};

use crate::ir::macros::{delegate, plain};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use crate::ir::traits::Threads;
use crate::ir::types::{Scalar, SquinType};

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

plain!(Threads, for Constant<Scalar, SquinType>);

plain!(Threads, for Arith<SquinType>);

plain!(Threads, for Cmp<SquinType>);
plain!(Threads, for Bitwise<SquinType>);

plain!(Threads, for If<SquinType>);

plain!(Threads, for For<SquinType>);

plain!(Threads, for Function<SquinType>, Return<SquinType>);

plain!(Threads, for Yield<SquinType>);
