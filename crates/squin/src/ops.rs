use crate::Type;
use kirin::prelude::*;
use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$alloc -> {wire:type}")]
pub struct Alloc {
    #[kirin(type = Type::Wire)]
    pub wire: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$free {wire}")]
pub struct Free {
    pub wire: SSAValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$h {wire} -> {wire_out:type}")]
pub struct H {
    pub wire: SSAValue,
    #[kirin(type = Type::Wire)]
    pub wire_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$cx {control}, {target} -> {control_out:type}, {target_out:type}")]
pub struct CX {
    pub control: SSAValue,
    pub target: SSAValue,
    #[kirin(type = Type::Wire)]
    pub control_out: ResultValue,
    #[kirin(type = Type::Wire)]
    pub target_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$rz({angle}) {wire} -> {wire_out:type}")]
pub struct Rz {
    /// The gate applies exp(-i * angle * Z / 2), with angle in radians.
    pub angle: f64,
    pub wire: SSAValue,
    #[kirin(type = Type::Wire)]
    pub wire_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$r({axis_angle}, {rotation_angle}) {wire} -> {wire_out:type}")]
pub struct R {
    /// The axis angle uses turns, with zero along X and one quarter along Y.
    pub axis_angle: f64,
    /// The rotation angle uses turns, with one turn equal to 2 * pi radians.
    pub rotation_angle: f64,
    pub wire: SSAValue,
    #[kirin(type = Type::Wire)]
    pub wire_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$cz {control}, {target} -> {control_out:type}, {target_out:type}")]
pub struct CZ {
    pub control: SSAValue,
    pub target: SSAValue,
    #[kirin(type = Type::Wire)]
    pub control_out: ResultValue,
    #[kirin(type = Type::Wire)]
    pub target_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$measure {wire} -> {wire_out:type}, {bit:type}")]
pub struct Measure {
    pub wire: SSAValue,
    #[kirin(type = Type::Wire)]
    pub wire_out: ResultValue,
    #[kirin(type = Type::Bit)]
    pub bit: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$reset {wire} -> {wire_out:type}")]
pub struct Reset {
    pub wire: SSAValue,
    #[kirin(type = Type::Wire)]
    pub wire_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$alloc_register {size} -> {register:type}")]
pub struct AllocRegister {
    pub size: SSAValue,
    #[kirin(type = Type::dynamic_register())]
    pub register: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$free_register {register}")]
pub struct FreeRegister {
    pub register: SSAValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$borrow {register}, {index} -> {register_out:type}, {wire:type}")]
pub struct Borrow {
    pub register: SSAValue,
    pub index: SSAValue,
    #[kirin(type = Type::dynamic_register())]
    pub register_out: ResultValue,
    #[kirin(type = Type::Wire)]
    pub wire: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$release {register}, {index}, {wire} -> {register_out:type}")]
pub struct Release {
    pub register: SSAValue,
    pub index: SSAValue,
    pub wire: SSAValue,
    #[kirin(type = Type::dynamic_register())]
    pub register_out: ResultValue,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "$length {register} -> {register_out:type}, {length:type}")]
pub struct Length {
    pub register: SSAValue,
    #[kirin(type = Type::dynamic_register())]
    pub register_out: ResultValue,
    #[kirin(type = Type::Int)]
    pub length: ResultValue,
}

pub type IntConstant = kirin_constant::Constant<i64, Type>;

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
#[chumsky(format = "fn {:name}{sig} {body}")]
pub struct Function {
    #[kirin(callable_body)]
    pub body: DiGraph,
    pub sig: Signature<Type>,
}

#[derive(Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, Serialize, Deserialize)]
#[kirin(builders, type = Type)]
pub enum Squin {
    #[wraps]
    Alloc(Alloc),
    #[wraps]
    Free(Free),
    #[wraps]
    H(H),
    #[wraps]
    CX(CX),
    #[wraps]
    Rz(Rz),
    #[wraps]
    R(R),
    #[wraps]
    CZ(CZ),
    #[wraps]
    Measure(Measure),
    #[wraps]
    Reset(Reset),
    #[wraps]
    AllocRegister(AllocRegister),
    #[wraps]
    FreeRegister(FreeRegister),
    #[wraps]
    Borrow(Borrow),
    #[wraps]
    Release(Release),
    #[wraps]
    Length(Length),
}

impl Squin {
    pub fn threads(&self) -> Vec<(SSAValue, ResultValue)> {
        match self {
            Self::H(op) => vec![(op.wire, op.wire_out)],
            Self::R(op) => vec![(op.wire, op.wire_out)],
            Self::Rz(op) => vec![(op.wire, op.wire_out)],
            Self::CZ(op) => vec![(op.control, op.control_out), (op.target, op.target_out)],
            Self::Reset(op) => vec![(op.wire, op.wire_out)],
            Self::Measure(op) => vec![(op.wire, op.wire_out)],
            Self::CX(op) => vec![(op.control, op.control_out), (op.target, op.target_out)],
            Self::Borrow(op) => vec![(op.register, op.register_out)],
            Self::Release(op) => vec![(op.register, op.register_out)],
            Self::Length(op) => vec![(op.register, op.register_out)],
            _ => Vec::new(),
        }
    }
}
