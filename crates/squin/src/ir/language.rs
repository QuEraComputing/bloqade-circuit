//! Compose the squin dialects with the Kirin dialects into one language.

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_bitwise::Bitwise;
use kirin_interpreter::Interpretable;

use kirin_cmp::Cmp;
use kirin_constant::Constant;

use kirin_function::{Function, Return};
use kirin_scf::StructuredControlFlow;

use crate::ir::dialects::circuit::Circuit;
use crate::ir::dialects::conditional::Conditional;
use crate::ir::dialects::gate::{self, Gate};
use crate::ir::dialects::measurement::{self, MeasurementOp};
use crate::ir::dialects::qubit::{self, QubitOp};
use crate::ir::dialects::register::{self, RegisterOp};
use crate::ir::dialects::repeat::Repeat;
use crate::ir::macros::delegate;
use crate::ir::types::{Scalar, SquinType};

/// Hold one statement of a squin kernel.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint, Interpretable)]
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
    #[wraps]
    Bitwise(Bitwise<SquinType>),
    #[wraps(lift_project_from(qubit::Alloc, qubit::Free, qubit::Measure, qubit::Reset))]
    Qubit(QubitOp),
    #[wraps(lift_project_from(
        register::AllocRegister,
        register::FreeRegister,
        register::Pack,
        register::Split,
        register::Join,
        register::LengthOf,
        register::MeasureRegister,
        register::Borrow,
        register::Release,
        register::Replace
    ))]
    Register(RegisterOp),
    #[wraps(lift_project_from(
        gate::X,
        gate::Y,
        gate::Z,
        gate::H,
        gate::S,
        gate::SDag,
        gate::T,
        gate::TDag,
        gate::SqrtX,
        gate::SqrtXDag,
        gate::SqrtY,
        gate::SqrtYDag,
        gate::Rx,
        gate::Ry,
        gate::Rz,
        gate::U3,
        gate::CX,
        gate::CY,
        gate::CZ
    ))]
    Gate(Gate),
    #[wraps(lift_project_from(
        measurement::PackResults,
        measurement::GetResult,
        measurement::ResultsLength,
        measurement::IsZero,
        measurement::IsOne,
        measurement::IsLost
    ))]
    Measurement(MeasurementOp),
    #[wraps]
    Circuit(Circuit),
    #[wraps]
    Conditional(Conditional),
    #[wraps]
    Repeat(Repeat),
}

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    Bitwise,
    Qubit,
    Register,
    Gate,
    Measurement,
    Circuit,
    Conditional,
    Repeat,
});
