//! Lower constants, arithmetic, comparisons, bitwise statements and measurement reads.
//!
//! Each classical result gets a local slot. A statement loads its operands,
//! runs one CPU instruction, and stores the result in its slot.

use kirin::prelude::*;
use kirin_arith::{Arith, ArithValue};
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;

use super::PpvmError;
use super::locals::Kind;
use super::writer::Writer;
use crate::analysis::address::Address;
use crate::ir::Squin;
use crate::ir::dialects::measurement::MeasurementOp;
use crate::ir::types::Scalar;

impl Writer<'_> {
    /// Write the classical statement `statement`.
    pub(super) fn classical(&mut self, statement: Statement) -> Result<(), PpvmError> {
        match statement.definition(self.program) {
            Squin::Constant(constant) => {
                let text = match constant.value {
                    Scalar::Number(ArithValue::I64(value)) => format!("i64, {value}"),
                    // `{:?}` keeps the decimal point, as in `1.0`.
                    Scalar::Number(ArithValue::F64(value)) => format!("f64, {value:?}"),
                    Scalar::Bool(value) => format!("bool, {value}"),
                    ref other => return Err(unsupported(&format!("the constant {other:?}"))),
                };
                self.line(format!("cpu::cpu.const {text}"));
                self.result(constant.result.into())?;
            }
            Squin::Arith(arith) => {
                let (operands, result, name) = match *arith {
                    Arith::Add { lhs, rhs, result } => (vec![lhs, rhs], result, "add"),
                    Arith::Sub { lhs, rhs, result } => (vec![lhs, rhs], result, "sub"),
                    Arith::Mul { lhs, rhs, result } => (vec![lhs, rhs], result, "mul"),
                    Arith::Div { lhs, rhs, result } => (vec![lhs, rhs], result, "div"),
                    Arith::Rem { lhs, rhs, result } => (vec![lhs, rhs], result, "rem"),
                    Arith::Neg { operand, result } => (vec![operand], result, "neg"),
                    _ => return Err(unsupported("this arithmetic statement")),
                };
                self.typed(&operands, result.into(), name)?;
            }
            Squin::Cmp(cmp) => {
                let (lhs, rhs, result, name) = match *cmp {
                    Cmp::Eq { lhs, rhs, result } => (lhs, rhs, result, "eq"),
                    Cmp::Ne { lhs, rhs, result } => (lhs, rhs, result, "ne"),
                    Cmp::Lt { lhs, rhs, result } => (lhs, rhs, result, "lt"),
                    Cmp::Le { lhs, rhs, result } => (lhs, rhs, result, "le"),
                    Cmp::Gt { lhs, rhs, result } => (lhs, rhs, result, "gt"),
                    Cmp::Ge { lhs, rhs, result } => (lhs, rhs, result, "ge"),
                    _ => return Err(unsupported("this comparison")),
                };
                let kind = self.kind(lhs)?;
                self.load(lhs)?;
                self.load(rhs)?;
                self.line(format!("cpu::cpu.{name} {kind}"));
                self.result(result.into())?;
            }
            Squin::Bitwise(bitwise) => self.bitwise(bitwise.clone())?,
            Squin::Measurement(measurement) => self.measurement(measurement.clone())?,
            other => {
                let name = format!("{other:?}");
                let name = name
                    .split('(')
                    .next()
                    .unwrap_or("this statement")
                    .to_string();
                return Err(unsupported(&format!("the statement {name}")));
            }
        }
        Ok(())
    }

    /// Write a bitwise statement.
    ///
    /// On `bool` values the CPU has `and`, `or`, `xor` and `not`. On `i64`
    /// values it has `bitand`, `bitor`, `bitxor`, `shl` and `shr`, and the
    /// writer forms `not` as `xor` with all bits set.
    fn bitwise(&mut self, bitwise: Bitwise<crate::ir::types::SquinType>) -> Result<(), PpvmError> {
        let (operands, result, name) = match bitwise {
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
        let result: SSAValue = result.into();
        for operand in &operands {
            self.load(*operand)?;
        }
        match (self.kind(result)?, name) {
            (Kind::Bool, _) => self.line(format!("cpu::cpu.{name}")),
            (kind, "not") => {
                self.line(format!("cpu::cpu.const {kind}, -1"));
                self.line(format!("cpu::cpu.bitxor {kind}"));
            }
            (kind, "shl" | "shr") => self.line(format!("cpu::cpu.{name} {kind}")),
            (kind, _) => self.line(format!("cpu::cpu.bit{name} {kind}")),
        }
        self.result(result)
    }

    /// Write a statement of the measurement dialect.
    ///
    /// ppvm encodes an outcome as a `u32`: 0 for zero, 1 for one and 2 for a lost atom.
    fn measurement(&mut self, measurement: MeasurementOp) -> Result<(), PpvmError> {
        match measurement {
            MeasurementOp::IsZero(read) => self.outcome(read.result, read.answer.into(), 0),
            MeasurementOp::IsOne(read) => self.outcome(read.result, read.answer.into(), 1),
            MeasurementOp::IsLost(read) => self.outcome(read.result, read.answer.into(), 2),
            MeasurementOp::Pack(pack) => {
                let slots = pack.results.iter().map(|result| self.slots(*result));
                let slots = slots.collect::<Result<Vec<_>, _>>()?.concat();
                self.locals.set(pack.packed.into(), slots);
                Ok(())
            }
            MeasurementOp::Get(get) => {
                let Address::Int(index) = self.addresses.of(get.index) else {
                    return Err(unsupported(
                        "`get_result` at an index that the analysis does not know",
                    ));
                };
                let slots = self.slots(get.results)?;
                let slot = usize::try_from(index)
                    .ok()
                    .and_then(|index| slots.get(index).copied());
                let slot = slot.ok_or_else(|| unsupported("`get_result` past the end"))?;
                self.locals.set(get.result.into(), vec![slot]);
                Ok(())
            }
            MeasurementOp::Length(length) => {
                let count = self.slots(length.results)?.len();
                self.line(format!("cpu::cpu.const i64, {count}"));
                self.result(length.length.into())
            }
        }
    }

    /// Compare the outcome in the slot of `result` with `code` and store the answer.
    fn outcome(&mut self, result: SSAValue, answer: SSAValue, code: u32) -> Result<(), PpvmError> {
        self.load(result)?;
        self.line(format!("cpu::cpu.const u32, {code}"));
        self.line("cpu::cpu.eq u32".to_string());
        self.result(answer)
    }

    /// Load `operands`, run `name` with the kind of `result`, and store the result.
    fn typed(
        &mut self,
        operands: &[SSAValue],
        result: SSAValue,
        name: &str,
    ) -> Result<(), PpvmError> {
        for operand in operands {
            self.load(*operand)?;
        }
        let kind = self.kind(result)?;
        self.line(format!("cpu::cpu.{name} {kind}"));
        self.result(result)
    }

    /// Give `result` a slot and pop the top of the stack into it.
    fn result(&mut self, result: SSAValue) -> Result<(), PpvmError> {
        self.define(result);
        self.store(result)
    }

    /// Return the kind of the classical `value`.
    fn kind(&self, value: SSAValue) -> Result<Kind, PpvmError> {
        let ty = *value.expect_info(self.program).ty();
        Kind::of(ty).ok_or_else(|| unsupported(&format!("a classical value of type {ty}")))
    }
}

fn unsupported(what: &str) -> PpvmError {
    PpvmError::Unsupported(what.to_string())
}
