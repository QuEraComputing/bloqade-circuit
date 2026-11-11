//! Compose the squin dialects with the Kirin dialects into one language.

use kirin::prelude::*;
use kirin_arith::Arith;

use kirin_cmp::Cmp;
use kirin_constant::Constant;

use kirin_function::{Function, Return};
use kirin_scf::StructuredControlFlow;

use crate::ir::macros::delegate;
use crate::ir::ops::{self, BitsOp, Gate, QubitOp, RegisterOp};
use crate::ir::types::{Scalar, SquinType};

/// Hold one statement of a squin kernel.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
pub enum Squin {
    #[wraps]
    Function(Function<SquinType>),
    #[wraps]
    Return(Return<SquinType>),
    #[wraps]
    Structured(StructuredControlFlow<SquinType>),
    #[wraps]
    Constant(Constant<Scalar, SquinType>),
    #[wraps]
    Arith(Arith<SquinType>),
    #[wraps]
    Cmp(Cmp<SquinType>),
    #[wraps(lift_project_from(ops::Alloc, ops::Free, ops::Measure, ops::Reset))]
    Qubit(QubitOp),
    #[wraps(lift_project_from(
        ops::AllocRegister,
        ops::FreeRegister,
        ops::Pack,
        ops::Split,
        ops::Join,
        ops::LengthOf,
        ops::MeasureRegister,
        ops::Borrow,
        ops::Release,
        ops::Replace
    ))]
    Register(RegisterOp),
    #[wraps(lift_project_from(
        ops::X,
        ops::Y,
        ops::Z,
        ops::H,
        ops::S,
        ops::SDag,
        ops::T,
        ops::TDag,
        ops::SqrtX,
        ops::SqrtXDag,
        ops::SqrtY,
        ops::SqrtYDag,
        ops::Rx,
        ops::Ry,
        ops::Rz,
        ops::U3,
        ops::CX,
        ops::CY,
        ops::CZ
    ))]
    Gate(Gate),
    #[wraps(lift_project_from(ops::BitsPack, ops::BitsGet, ops::BitsLength))]
    Bits(BitsOp),
}

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    Qubit,
    Register,
    Gate,
    Bits,
});
