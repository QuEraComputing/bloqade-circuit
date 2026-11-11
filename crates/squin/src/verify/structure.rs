//! Tell the ownership rules how each statement nests blocks, lends a register
//! element, or computes an index.

use kirin::prelude::*;
use kirin_arith::Arith;
use kirin_cmp::Cmp;
use kirin_constant::Constant;
use kirin_function::{Function, Return};
use kirin_scf::{For, If, StructuredControlFlow, Yield};

use crate::ir::Squin;
use crate::ir::dialects::bits::{BitsGet, BitsLength, BitsOp, BitsPack};
use crate::ir::dialects::gate::*;
use crate::ir::dialects::qubit::{Alloc, Free, Measure, QubitOp, Reset};
use crate::ir::dialects::register::{
    AllocRegister, Borrow, FreeRegister, Join, LengthOf, MeasureRegister, Pack, RegisterOp,
    Release, Replace, Split,
};
use crate::ir::macros::plain;
use crate::ir::types::{Scalar, SquinType};

/// Tell how a statement runs the blocks that it owns.
pub enum Nesting<'a> {
    /// The statement owns no block.
    Flat,
    /// The statement runs exactly one of the two blocks, as an `if` does.
    Arms([Block; 2]),
    /// The statement runs `body` any number of times, as a `for` does.
    ///
    /// `initial` holds the values that the first run receives after the loop
    /// index. Result `i` of the statement continues `initial[i]`.
    Loop {
        body: Block,
        initial: &'a [SSAValue],
    },
}

/// Describe a statement that takes an element out of a register or puts it back.
pub enum Lending {
    /// The statement lends the element at `index` to `wire` and makes `slot`.
    Borrow {
        register: SSAValue,
        index: SSAValue,
        register_out: ResultValue,
        slot: ResultValue,
        wire: ResultValue,
    },
    /// The statement consumes `slot` and fills its element with `wire`.
    Release {
        register: SSAValue,
        slot: SSAValue,
        wire: SSAValue,
    },
}

/// Describe a statement whose result is an integer that the verifier can compare.
pub enum Offset {
    /// The result is this constant.
    Constant(i64),
    /// The result is the sum of the two values.
    Sum(SSAValue, SSAValue),
    /// The result is the first value minus the second value.
    Difference(SSAValue, SSAValue),
}

/// Give the ownership rules the facts that they need about a statement.
///
/// Each default is for a statement that owns no block, lends no element and
/// gives no integer that the verifier can compare.
pub trait Structure {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Flat
    }

    fn lending(&self) -> Option<Lending> {
        None
    }

    fn offset(&self) -> Option<Offset> {
        None
    }
}

/// Implement `Structure` for an enum that wraps one statement in each variant.
macro_rules! delegate {
    ($wrapper:ty { $($variant:ident),+ $(,)? }) => {
        impl Structure for $wrapper {
            fn nesting(&self) -> Nesting<'_> {
                match self {
                    $(Self::$variant(inner) => inner.nesting(),)+
                }
            }

            fn lending(&self) -> Option<Lending> {
                match self {
                    $(Self::$variant(inner) => inner.lending(),)+
                }
            }

            fn offset(&self) -> Option<Offset> {
                match self {
                    $(Self::$variant(inner) => inner.offset(),)+
                }
            }
        }
    };
}

delegate!(QubitOp {
    Alloc,
    Free,
    Measure,
    Reset
});

delegate!(RegisterOp {
    AllocRegister,
    FreeRegister,
    Pack,
    Split,
    Join,
    LengthOf,
    MeasureRegister,
    Borrow,
    Release,
    Replace,
});

delegate!(BitsOp { Pack, Get, Length });

delegate!(StructuredControlFlow<SquinType> { If, For, Yield });

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    Qubit,
    Register,
    Gate,
    Bits,
});

/// Give every gate the default answers, because a gate owns no block and lends no element.
macro_rules! flat {
    ($($name:ident $(($($angle:ident),+))?;)+) => {
        plain!(Structure, for $($name),+);
        delegate!(Gate { $($name),+ });
    };
}

for_each_gate!(flat);

plain!(Structure, for Alloc, Free, Measure, Reset);
plain!(Structure, for AllocRegister, FreeRegister, Pack, Split, Join, LengthOf, MeasureRegister);
plain!(Structure, for Replace);
plain!(Structure, for BitsPack, BitsGet, BitsLength);
plain!(Structure, for Cmp<SquinType>);
plain!(Structure, for Function<SquinType>, Return<SquinType>);
plain!(Structure, for Yield<SquinType>);

impl Structure for Borrow {
    fn lending(&self) -> Option<Lending> {
        Some(Lending::Borrow {
            register: self.register,
            index: self.index,
            register_out: self.register_out,
            slot: self.slot,
            wire: self.wire,
        })
    }
}

impl Structure for Release {
    fn lending(&self) -> Option<Lending> {
        Some(Lending::Release {
            register: self.register,
            slot: self.slot,
            wire: self.wire,
        })
    }
}

impl Structure for Constant<Scalar, SquinType> {
    fn offset(&self) -> Option<Offset> {
        match self.value {
            Scalar::Int(value) => Some(Offset::Constant(value)),
            _ => None,
        }
    }
}

impl Structure for Arith<SquinType> {
    fn offset(&self) -> Option<Offset> {
        match *self {
            Arith::Add { lhs, rhs, .. } => Some(Offset::Sum(lhs, rhs)),
            Arith::Sub { lhs, rhs, .. } => Some(Offset::Difference(lhs, rhs)),
            _ => None,
        }
    }
}

impl Structure for If<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Arms([self.then_block(), self.else_block()])
    }
}

impl Structure for For<SquinType> {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Loop {
            body: self.body(),
            initial: self.init_args(),
        }
    }
}
