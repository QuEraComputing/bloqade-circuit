//! Evaluate Kirin numeric values with checked integer operations and native floating-point operations.

use kirin_arith::ArithValue;
use std::cmp::Ordering;

use super::Failure;

#[derive(Clone, Copy)]
pub(super) enum Binary {
    Add,
    Sub,
    Mul,
    Div,
    Rem,
}

pub(super) fn binary(
    op: Binary,
    left: ArithValue,
    right: ArithValue,
) -> Result<ArithValue, Failure> {
    macro_rules! evaluate {
        (integers: $($int:ident),+; floats: $($float:ident),+) => {
            match (left, right) {
                $((ArithValue::$int(a), ArithValue::$int(b)) => {
                    let result = match op {
                        Binary::Add => a.checked_add(b),
                        Binary::Sub => a.checked_sub(b),
                        Binary::Mul => a.checked_mul(b),
                        Binary::Div => a.checked_div(b),
                        Binary::Rem => a.checked_rem(b),
                    };
                    result.map(ArithValue::$int).ok_or(Failure::Arithmetic)
                },)+
                $((ArithValue::$float(a), ArithValue::$float(b)) => {
                    let result = match op {
                        Binary::Add => a + b,
                        Binary::Sub => a - b,
                        Binary::Mul => a * b,
                        Binary::Div => a / b,
                        Binary::Rem => a % b,
                    };
                    Ok(ArithValue::$float(result))
                },)+
                _ => Err(mismatched()),
            }
        };
    }
    evaluate!(integers: I8, I16, I32, I64, I128, U8, U16, U32, U64, U128; floats: F32, F64)
}

pub(super) fn negate(value: ArithValue) -> Result<ArithValue, Failure> {
    macro_rules! evaluate {
        ($($variant:ident),+) => {
            match value {
                $(ArithValue::$variant(value) => value.checked_neg()
                    .map(ArithValue::$variant).ok_or(Failure::Arithmetic),)+
                ArithValue::F32(value) => Ok(ArithValue::F32(-value)),
                ArithValue::F64(value) => Ok(ArithValue::F64(-value)),
            }
        };
    }
    evaluate!(I8, I16, I32, I64, I128, U8, U16, U32, U64, U128)
}

pub(super) fn compare(left: ArithValue, right: ArithValue) -> Result<Option<Ordering>, Failure> {
    macro_rules! evaluate {
        ($($variant:ident),+) => {
            match (left, right) {
                $((ArithValue::$variant(a), ArithValue::$variant(b)) => Ok(a.partial_cmp(&b)),)+
                _ => Err(mismatched()),
            }
        };
    }
    evaluate!(I8, I16, I32, I64, I128, U8, U16, U32, U64, U128, F32, F64)
}

fn mismatched() -> Failure {
    Failure::Kind {
        expected: "two numbers of the same type",
        found: "numbers with different types",
    }
}
