//! Write Kirin's constants, arithmetic, comparisons, bitwise statements and functions.
//!
//! A constant becomes a literal at each use. Every other classical result
//! gets a Python name and one assignment.

use kirin::prelude::*;
use kirin_arith::{Arith, ArithType, ArithValue};
use kirin_bitwise::Bitwise;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_interpreter::dialect::Interpretable;

use crate::emit::python::{EmitPython, Py, PythonEmitter, PythonError};
use crate::ir::types::{Scalar, SquinType};

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Constant<Scalar, SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let py = match self.value {
            Scalar::Number(ArithValue::I64(value)) => Py {
                text: value.to_string(),
                number: Some(value as f64),
            },
            // `{:?}` keeps the decimal point, as in `1.0`.
            Scalar::Number(ArithValue::F64(value)) => Py {
                text: format!("{value:?}"),
                number: Some(value),
            },
            Scalar::Bool(true) => Py::expr("True"),
            Scalar::Bool(false) => Py::expr("False"),
            ref other => {
                return Err(PythonError::Unsupported(format!("the constant {other:?}")));
            }
        };
        emitter.bind(self.result.into(), py)
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Arith<SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (lhs, rhs, result, operator) = match *self {
            Arith::Add { lhs, rhs, result } => (lhs, rhs, result, "+"),
            Arith::Sub { lhs, rhs, result } => (lhs, rhs, result, "-"),
            Arith::Mul { lhs, rhs, result } => (lhs, rhs, result, "*"),
            Arith::Div { lhs, rhs, result } => {
                return divide(emitter, [lhs, rhs], result.into(), "trunc_div", None);
            }
            Arith::Rem { lhs, rhs, result } => {
                return divide(
                    emitter,
                    [lhs, rhs],
                    result.into(),
                    "trunc_rem",
                    Some("math.fmod"),
                );
            }
            Arith::Neg { operand, result } => {
                let operand = emitter.text(operand)?;
                return emitter.assign(result.into(), &format!("-{operand}"));
            }
            _ => return Err(PythonError::Unsupported("this arithmetic statement".into())),
        };
        binary(emitter, lhs, rhs, result.into(), operator)
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Cmp<SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (lhs, rhs, result, operator) = match *self {
            Cmp::Eq { lhs, rhs, result } => (lhs, rhs, result, "=="),
            Cmp::Ne { lhs, rhs, result } => (lhs, rhs, result, "!="),
            Cmp::Lt { lhs, rhs, result } => (lhs, rhs, result, "<"),
            Cmp::Le { lhs, rhs, result } => (lhs, rhs, result, "<="),
            Cmp::Gt { lhs, rhs, result } => (lhs, rhs, result, ">"),
            Cmp::Ge { lhs, rhs, result } => (lhs, rhs, result, ">="),
            _ => return Err(PythonError::Unsupported("this comparison".into())),
        };
        binary(emitter, lhs, rhs, result.into(), operator)
    }
}

/// Write a bitwise statement with the Python operator for its result type.
///
/// On `bool` values the operators are `and`, `or`, `^` and `not`. On
/// integers they are `&`, `|`, `^`, `~`, `<<` and `>>`.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Bitwise<SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let boolean = |emitter: &PythonEmitter<'a>, result: ResultValue| {
            *SSAValue::from(result).expect_info(emitter.program).ty() == SquinType::Bool
        };
        let (lhs, rhs, result, operator) = match self.clone() {
            Bitwise::And {
                lhs, rhs, result, ..
            } => {
                let operator = if boolean(emitter, result) { "and" } else { "&" };
                (lhs, rhs, result, operator)
            }
            Bitwise::Or {
                lhs, rhs, result, ..
            } => {
                let operator = if boolean(emitter, result) { "or" } else { "|" };
                (lhs, rhs, result, operator)
            }
            Bitwise::Xor {
                lhs, rhs, result, ..
            } => (lhs, rhs, result, "^"),
            Bitwise::Shl {
                lhs, rhs, result, ..
            } => (lhs, rhs, result, "<<"),
            Bitwise::Shr {
                lhs, rhs, result, ..
            } => (lhs, rhs, result, ">>"),
            Bitwise::Not {
                operand, result, ..
            } => {
                let operator = if boolean(emitter, result) {
                    "not "
                } else {
                    "~"
                };
                let operand = emitter.text(operand)?;
                return emitter.assign(result.into(), &format!("{operator}{operand}"));
            }
            _ => return Err(PythonError::Unsupported("this bitwise statement".into())),
        };
        binary(emitter, lhs, rhs, result.into(), operator)
    }
}

/// Write a division or a remainder that rounds toward zero, as Kirin's does.
///
/// On integers the rule calls `integer`, a helper that the module defines.
/// On floats, a division writes `lhs / rhs`, which already matches. A float
/// remainder calls `float`, here `math.fmod`, whose sign follows the dividend
/// as Rust's `%` does.
fn divide(
    emitter: &mut PythonEmitter<'_>,
    [lhs, rhs]: [SSAValue; 2],
    result: SSAValue,
    integer: &str,
    float: Option<&str>,
) -> Result<(), PythonError> {
    let (lhs, rhs) = (emitter.text(lhs)?, emitter.text(rhs)?);
    let ty = *result.expect_info(emitter.program).ty();
    let expression = match float {
        _ if ty == SquinType::Number(ArithType::I64) => {
            emitter.uses_trunc = true;
            format!("{integer}({lhs}, {rhs})")
        }
        None => format!("{lhs} / {rhs}"),
        Some(function) => {
            emitter.uses_math = true;
            format!("{function}({lhs}, {rhs})")
        }
    };
    emitter.assign(result, &expression)
}

/// Write `result = lhs operator rhs`.
fn binary(
    emitter: &mut PythonEmitter<'_>,
    lhs: SSAValue,
    rhs: SSAValue,
    result: SSAValue,
    operator: &str,
) -> Result<(), PythonError> {
    let (lhs, rhs) = (emitter.text(lhs)?, emitter.text(rhs)?);
    emitter.assign(result, &format!("{lhs} {operator} {rhs}"))
}

/// Write nothing, because `emit` writes the `def` line of the function.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Function<SquinType> {
    fn interpret(&self, _emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        Ok(())
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Return<SquinType> {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let values: Vec<SSAValue> = self.arguments().copied().collect();
        let values = values.into_iter().map(|value| emitter.text(value));
        let values = values.collect::<Result<Vec<_>, _>>()?;
        emitter.line(format!("return {}", values.join(", ")).trim_end());
        Ok(())
    }
}
