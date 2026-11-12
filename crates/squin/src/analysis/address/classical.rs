//! Give the address lattice the traits that Kirin's classical rules need.
//!
//! The rules of `kirin-constant`, `kirin-arith`, `kirin-cmp` and `kirin-scf`
//! read and write `Address` values through these traits. Integer facts stay
//! known, which keeps register indices known. Every other fact becomes `Top`.

use std::ops::{Add, Mul, Neg, Sub};

use kirin_arith::{ArithValue, CheckedDiv, CheckedRem};
use kirin_cmp::CompareValue;
use kirin_interpreter::BranchCondition;
use kirin_scf::ForLoopValue;

use super::Address;
use crate::ir::types::Scalar;

impl Address {
    /// Combine two integers with `op`, and give `Top` for any other pair.
    fn integers(self, rhs: Self, op: impl FnOnce(i64, i64) -> Option<i64>) -> Self {
        match (self, rhs) {
            (Address::Int(lhs), Address::Int(rhs)) => {
                op(lhs, rhs).map_or(Address::Top, Address::Int)
            }
            (Address::Bottom, _) | (_, Address::Bottom) => Address::Bottom,
            _ => Address::Top,
        }
    }

    /// Compare two integers or two truth values with `op`.
    fn compared(&self, rhs: &Self, op: impl FnOnce(std::cmp::Ordering) -> bool) -> Self {
        match (self, rhs) {
            (Address::Int(lhs), Address::Int(rhs)) => Address::Bool(op(lhs.cmp(rhs))),
            (Address::Bool(lhs), Address::Bool(rhs)) => Address::Bool(op(lhs.cmp(rhs))),
            (Address::Bottom, _) | (_, Address::Bottom) => Address::Bottom,
            _ => Address::Top,
        }
    }
}

/// Keep integer and truth constants, and forget float constants.
impl From<Scalar> for Address {
    fn from(scalar: Scalar) -> Self {
        match scalar {
            Scalar::Number(ArithValue::I64(value)) => Address::Int(value),
            Scalar::Bool(value) => Address::Bool(value),
            Scalar::Number(_) => Address::Top,
        }
    }
}

impl Add for Address {
    type Output = Address;
    fn add(self, rhs: Self) -> Self {
        self.integers(rhs, i64::checked_add)
    }
}

impl Sub for Address {
    type Output = Address;
    fn sub(self, rhs: Self) -> Self {
        self.integers(rhs, i64::checked_sub)
    }
}

impl Mul for Address {
    type Output = Address;
    fn mul(self, rhs: Self) -> Self {
        self.integers(rhs, i64::checked_mul)
    }
}

impl Neg for Address {
    type Output = Address;
    fn neg(self) -> Self {
        match self {
            Address::Int(value) => value.checked_neg().map_or(Address::Top, Address::Int),
            Address::Bottom => Address::Bottom,
            _ => Address::Top,
        }
    }
}

/// Divide two integers. The result is `None` only for a known division by zero.
impl CheckedDiv for Address {
    fn checked_div(self, rhs: Self) -> Option<Self> {
        match rhs {
            Address::Int(0) => None,
            rhs => Some(self.integers(rhs, i64::checked_div)),
        }
    }
}

impl CheckedRem for Address {
    fn checked_rem(self, rhs: Self) -> Option<Self> {
        match rhs {
            Address::Int(0) => None,
            rhs => Some(self.integers(rhs, i64::checked_rem)),
        }
    }
}

impl CompareValue for Address {
    type Bool = Address;

    fn cmp_eq(&self, other: &Self) -> Address {
        self.compared(other, |order| order.is_eq())
    }

    fn cmp_ne(&self, other: &Self) -> Address {
        self.compared(other, |order| order.is_ne())
    }

    fn cmp_lt(&self, other: &Self) -> Address {
        self.compared(other, |order| order.is_lt())
    }

    fn cmp_le(&self, other: &Self) -> Address {
        self.compared(other, |order| order.is_le())
    }

    fn cmp_gt(&self, other: &Self) -> Address {
        self.compared(other, |order| order.is_gt())
    }

    fn cmp_ge(&self, other: &Self) -> Address {
        self.compared(other, |order| order.is_ge())
    }
}

impl BranchCondition for Address {
    fn is_truthy(&self) -> Option<bool> {
        match self {
            Address::Bool(value) => Some(*value),
            _ => None,
        }
    }
}

impl ForLoopValue for Address {
    fn loop_condition(&self, end: &Self) -> Option<bool> {
        match (self, end) {
            (Address::Int(index), Address::Int(end)) => Some(index < end),
            _ => None,
        }
    }

    fn loop_step(&self, step: &Self) -> Option<Self> {
        match (self, step) {
            (Address::Int(index), Address::Int(step)) => index.checked_add(*step).map(Address::Int),
            (Address::Bottom, _) | (_, Address::Bottom) => Some(Address::Bottom),
            _ => Some(Address::Top),
        }
    }
}
