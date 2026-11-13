//! Write Kirin's constants, arithmetic, comparisons and bitwise statements.
//!
//! A rule loads its operands, runs one CPU instruction, and stores the
//! result in a new slot.

use kirin_arith::{Arith, ArithValue};
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_interpreter::dialect::Interpretable;

use super::unsupported;
use crate::emit::ppvm::locals::Kind;
use crate::emit::ppvm::{EmitPpvm, PpvmEmitter, PpvmError};
use crate::ir::types::{Scalar, SquinType};

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Constant<Scalar, SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let text = match self.value {
            Scalar::Number(ArithValue::I64(value)) => format!("i64, {value}"),
            // `{:?}` keeps the decimal point, as in `1.0`.
            Scalar::Number(ArithValue::F64(value)) => format!("f64, {value:?}"),
            Scalar::Bool(value) => format!("bool, {value}"),
            ref other => return Err(unsupported(&format!("the constant {other:?}"))),
        };
        emitter.line(format!("cpu::cpu.const {text}"));
        emitter.result(self.result.into())
    }
}

impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Arith<SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let (operands, result, name) = match *self {
            Arith::Add { lhs, rhs, result } => (vec![lhs, rhs], result, "add"),
            Arith::Sub { lhs, rhs, result } => (vec![lhs, rhs], result, "sub"),
            Arith::Mul { lhs, rhs, result } => (vec![lhs, rhs], result, "mul"),
            Arith::Div { lhs, rhs, result } => (vec![lhs, rhs], result, "div"),
            Arith::Rem { lhs, rhs, result } => (vec![lhs, rhs], result, "rem"),
            Arith::Neg { operand, result } => (vec![operand], result, "neg"),
            _ => return Err(unsupported("this arithmetic statement")),
        };
        emitter.typed(&operands, result.into(), name)
    }
}

/// Compare two values with the CPU instruction for the kind of the left operand.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Cmp<SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let (lhs, rhs, result, name) = match *self {
            Cmp::Eq { lhs, rhs, result } => (lhs, rhs, result, "eq"),
            Cmp::Ne { lhs, rhs, result } => (lhs, rhs, result, "ne"),
            Cmp::Lt { lhs, rhs, result } => (lhs, rhs, result, "lt"),
            Cmp::Le { lhs, rhs, result } => (lhs, rhs, result, "le"),
            Cmp::Gt { lhs, rhs, result } => (lhs, rhs, result, "gt"),
            Cmp::Ge { lhs, rhs, result } => (lhs, rhs, result, "ge"),
            _ => return Err(unsupported("this comparison")),
        };
        let kind = emitter.kind(lhs)?;
        emitter.load(lhs)?;
        emitter.load(rhs)?;
        emitter.line(format!("cpu::cpu.{name} {kind}"));
        emitter.result(result.into())
    }
}

/// Write a bitwise statement.
///
/// On `bool` values the CPU has `and`, `or`, `xor` and `not`. On `i64`
/// values it has `bitand`, `bitor`, `bitxor`, `shl` and `shr`, and the rule
/// forms `not` as `xor` with all bits set.
impl<'a> Interpretable<PpvmEmitter<'a>, EmitPpvm> for Bitwise<SquinType> {
    fn interpret(&self, emitter: &mut PpvmEmitter<'a>) -> Result<(), PpvmError> {
        let (operands, result, name) = match self.clone() {
            Bitwise::And {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, "and"),
            Bitwise::Or {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, "or"),
            Bitwise::Xor {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, "xor"),
            Bitwise::Not {
                operand, result, ..
            } => (vec![operand], result, "not"),
            Bitwise::Shl {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, "shl"),
            Bitwise::Shr {
                lhs, rhs, result, ..
            } => (vec![lhs, rhs], result, "shr"),
            _ => return Err(unsupported("this bitwise statement")),
        };
        for operand in &operands {
            emitter.load(*operand)?;
        }
        let result = result.into();
        match (emitter.kind(result)?, name) {
            (Kind::Bool, _) => emitter.line(format!("cpu::cpu.{name}")),
            (kind, "not") => {
                emitter.line(format!("cpu::cpu.const {kind}, -1"));
                emitter.line(format!("cpu::cpu.bitxor {kind}"));
            }
            (kind, "shl" | "shr") => emitter.line(format!("cpu::cpu.{name} {kind}")),
            (kind, _) => emitter.line(format!("cpu::cpu.bit{name} {kind}")),
        }
        emitter.result(result)
    }
}
