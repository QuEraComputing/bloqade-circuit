use super::{ValidationError, Value};
use crate::{Squin, Type, ops::Function};
use kirin_interpreter::{ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp};
use std::collections::BTreeSet;

fn wire(value: Value) -> Result<Value, ValidationError> {
    if value != Value::Scalar(Type::Wire) {
        return Err(ValidationError::new("The operation requires Wire."));
    }
    Ok(value)
}

fn register(value: Value) -> Result<Value, ValidationError> {
    if !matches!(value, Value::Register { .. }) {
        return Err(ValidationError::new("The operation requires a register."));
    }
    Ok(value)
}

fn integer(value: Value) -> Result<Option<i64>, ValidationError> {
    match value {
        Value::Int(value) => Ok(value),
        _ => Err(ValidationError::new("The operation requires Int.")),
    }
}

fn index(value: Value, length: Option<u64>) -> Result<u64, ValidationError> {
    let index = integer(value)?.ok_or_else(|| {
        ValidationError::new("The checker cannot prove the index bounds or slot separation.")
    })?;
    let index = u64::try_from(index)
        .map_err(|_| ValidationError::new("The register index must be nonnegative."))?;
    let length = length.ok_or_else(|| {
        ValidationError::new("The checker cannot prove bounds for a register with unknown length.")
    })?;
    if index >= length {
        return Err(ValidationError::new(format!(
            "Index {index} exceeds the bounds of a register with length {length}."
        )));
    }
    Ok(index)
}

impl<I> Interpretable<I, ForwardEval> for Squin
where
    I: SparseForwardInterp<Value = Value, Error = ValidationError>,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        match self {
            Self::Alloc(op) => interp.write(op.wire, Value::Scalar(Type::Wire))?,
            Self::Free(op) => {
                wire(interp.read(op.wire)?)?;
            }
            Self::H(_)
            | Self::Reset(_)
            | Self::CX(_)
            | Self::CZ(_)
            | Self::Rz(_)
            | Self::R(_)
            | Self::Measure(_) => {
                if let Self::Rz(op) = self {
                    if !op.angle.is_finite() {
                        return Err(ValidationError::new(
                            "The Rz angle must be finite and use radians.",
                        ));
                    }
                }
                if let Self::R(op) = self {
                    if !op.axis_angle.is_finite() {
                        return Err(ValidationError::new(
                            "The R axis angle must be finite and use turns.",
                        ));
                    }
                    if !op.rotation_angle.is_finite() {
                        return Err(ValidationError::new(
                            "The R rotation angle must be finite and use turns.",
                        ));
                    }
                }
                for (input, output) in self.threads() {
                    let value = wire(interp.read(input)?)?;
                    interp.write(output, value)?;
                }
                if let Self::Measure(op) = self {
                    interp.write(op.bit, Value::Scalar(Type::Bit))?;
                }
            }
            Self::AllocRegister(op) => {
                let size = integer(interp.read(op.size)?)?
                    .and_then(|n| u64::try_from(n).ok())
                    .ok_or_else(|| {
                        ValidationError::new(
                            "The checker requires a proven nonnegative allocation size.",
                        )
                    })?;
                interp.write(
                    op.register,
                    Value::Register {
                        declared: None,
                        length: Some(size),
                        empty: BTreeSet::new(),
                    },
                )?;
            }
            Self::FreeRegister(op) => interp.read(op.register)?.full()?,
            Self::Borrow(op) => {
                let mut state = register(interp.read(op.register)?)?;
                let Value::Register { length, empty, .. } = &mut state else {
                    unreachable!()
                };
                let index = index(interp.read(op.index)?, *length)?;
                if !empty.insert(index) {
                    return Err(ValidationError::new(format!(
                        "Slot {index} is already empty. A second borrow requires a release."
                    )));
                }
                interp.write(op.register_out, state)?;
                interp.write(op.wire, Value::Scalar(Type::Wire))?;
            }
            Self::Release(op) => {
                let mut state = register(interp.read(op.register)?)?;
                wire(interp.read(op.wire)?)?;
                let Value::Register { length, empty, .. } = &mut state else {
                    unreachable!()
                };
                let index = index(interp.read(op.index)?, *length)?;
                if !empty.remove(&index) {
                    return Err(ValidationError::new(format!(
                        "Slot {index} is occupied. A release requires an empty slot."
                    )));
                }
                interp.write(op.register_out, state)?;
            }
            Self::Length(op) => {
                let state = register(interp.read(op.register)?)?;
                let Value::Register { length, .. } = &state else {
                    unreachable!()
                };
                interp.write(op.length, Value::Int(length.map(|n| n as i64)))?;
                interp.write(op.register_out, state)?;
            }
        }
        Ok(SparseForwardEffect::Next)
    }
}

impl<I> Interpretable<I, ForwardEval> for Function
where
    I: SparseForwardInterp<Value = Value, Error = ValidationError>,
{
    fn interpret(&self, _: &mut I) -> Result<I::Effect, I::Error> {
        Err(ValidationError::new(
            "The checker does not support nested functions.",
        ))
    }
}
