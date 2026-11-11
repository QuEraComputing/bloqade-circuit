//! Give the verifier the facts about blocks, borrows and indices of a statement.

use kirin::prelude::{Block, ResultValue, SSAValue};

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

/// Give the verifier the facts about a statement that its rules need.
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
