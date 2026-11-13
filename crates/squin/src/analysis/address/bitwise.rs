//! Give the address lattice the traits that Kirin's bitwise rules need.
//!
//! Truth values and integers stay known, so a program that combines the
//! answers of `is_zero`, `is_one` and `is_lost` keeps a known fact where the
//! answers are known. Every other fact becomes `Top`.

use std::ops::{BitAnd, BitOr, BitXor, Not};

use kirin_bitwise::{CheckedShl, CheckedShr};

use super::Address;

impl Address {
    /// Combine two truth values with `truth` or two integers with `integer`.
    fn logical(
        self,
        rhs: Self,
        truth: fn(bool, bool) -> bool,
        integer: fn(i64, i64) -> i64,
    ) -> Self {
        match (self, rhs) {
            (Address::Bool(lhs), Address::Bool(rhs)) => Address::Bool(truth(lhs, rhs)),
            (Address::Int(lhs), Address::Int(rhs)) => Address::Int(integer(lhs, rhs)),
            (Address::Bottom, _) | (_, Address::Bottom) => Address::Bottom,
            _ => Address::Top,
        }
    }

    /// Shift an integer by a known amount with `op`.
    ///
    /// The result is `None` if the shift leaves the range of the integer, and
    /// Kirin reports that as an error.
    fn shifted(self, rhs: Self, op: fn(i64, u32) -> Option<i64>) -> Option<Self> {
        match (self, rhs) {
            (Address::Int(lhs), Address::Int(rhs)) => {
                let amount = u32::try_from(rhs).ok()?;
                op(lhs, amount).map(Address::Int)
            }
            (Address::Bottom, _) | (_, Address::Bottom) => Some(Address::Bottom),
            _ => Some(Address::Top),
        }
    }
}

impl BitAnd for Address {
    type Output = Address;
    fn bitand(self, rhs: Self) -> Self {
        self.logical(rhs, |a, b| a & b, |a, b| a & b)
    }
}

impl BitOr for Address {
    type Output = Address;
    fn bitor(self, rhs: Self) -> Self {
        self.logical(rhs, |a, b| a | b, |a, b| a | b)
    }
}

impl BitXor for Address {
    type Output = Address;
    fn bitxor(self, rhs: Self) -> Self {
        self.logical(rhs, |a, b| a ^ b, |a, b| a ^ b)
    }
}

impl Not for Address {
    type Output = Address;
    fn not(self) -> Self {
        match self {
            Address::Bool(value) => Address::Bool(!value),
            Address::Int(value) => Address::Int(!value),
            Address::Bottom => Address::Bottom,
            _ => Address::Top,
        }
    }
}

impl CheckedShl for Address {
    fn checked_shl(self, rhs: Self) -> Option<Self> {
        self.shifted(rhs, i64::checked_shl)
    }
}

impl CheckedShr for Address {
    fn checked_shr(self, rhs: Self) -> Option<Self> {
        self.shifted(rhs, i64::checked_shr)
    }
}
