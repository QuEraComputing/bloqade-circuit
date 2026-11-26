use crate::{Squin, Type, ops};
use kirin::prelude::*;
use kirin_interpreter::Interpretable;

#[derive(
    Clone,
    Debug,
    PartialEq,
    Dialect,
    HasParser,
    PrettyPrint,
    Interpretable,
    serde::Serialize,
    serde::Deserialize,
)]
#[kirin(builders, type = Type)]
pub enum Circuit {
    #[wraps(lift_project_from(
        ops::Alloc,
        ops::Free,
        ops::H,
        ops::CX,
        ops::Rz,
        ops::R,
        ops::CZ,
        ops::Measure,
        ops::Reset,
        ops::AllocRegister,
        ops::FreeRegister,
        ops::Borrow,
        ops::Release,
        ops::Length
    ))]
    Squin(Squin),
    #[wraps]
    Constant(ops::IntConstant),
    #[wraps]
    Function(ops::Function),
}
