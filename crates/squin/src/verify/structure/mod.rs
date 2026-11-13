//! Describe block nesting, register borrowing, and integer expressions for the ownership checks.

use kirin::prelude::*;

use crate::ir::Squin;

/// Tell how a statement runs the blocks that it owns.
pub enum Nesting<'a> {
    /// The statement owns no block.
    Flat,
    /// The statement runs exactly one of the two blocks, as an `if` does.
    ///
    /// Each arm receives `inputs` as its block arguments. A Kirin `if` has no
    /// inputs, and a squin `conditional` hands its wires to the arms this way.
    Arms {
        arms: [Block; 2],
        inputs: &'a [SSAValue],
    },
    /// The statement runs the dataflow graph `body` once, as a `circuit` does.
    ///
    /// Port `k` of the graph receives `inputs[k]`, and result `i` of the
    /// statement is yield `i` of the graph.
    Graph {
        body: DiGraph,
        inputs: &'a [SSAValue],
    },
    /// The statement runs `body` any number of times, as a `for` and a `repeat` do.
    ///
    /// The body receives `leading_arguments` arguments before its carried
    /// values, and it yields `leading_yields` values before them. A `for` has
    /// the loop index as its one leading argument. A `repeat` has the stop
    /// flag as its one leading yield. `initial` holds the carried values of
    /// the first run, and result `i` of the statement continues `initial[i]`.
    Loop {
        body: Block,
        initial: &'a [SSAValue],
        leading_arguments: usize,
        leading_yields: usize,
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

/// Tell where a statement may sit.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Place {
    /// The statement sits in a block, as control flow and register statements do.
    Block,
    /// The statement sits in the graph of a `circuit` region, as a gate does.
    Graph,
    /// The statement sits in a block or in a graph, as a constant does.
    Anywhere,
}

/// Give the ownership rules the facts that they need about a statement.
///
/// Each default is for a statement that sits in a block, owns no block, lends
/// no element and gives no integer that the verifier can compare.
pub trait Structure {
    fn place(&self) -> Place {
        Place::Block
    }

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
            fn place(&self) -> Place {
                match self {
                    $(Self::$variant(inner) => inner.place(),)+
                }
            }

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

/// Implement `Structure` with the place `$place` and the other defaults for each listed type.
macro_rules! placed {
    ($place:ident, for $($statement:ty),+ $(,)?) => {
        $(impl Structure for $statement {
            fn place(&self) -> Place {
                Place::$place
            }
        })+
    };
}

mod circuit;
mod conditional;
mod from_kirin;
mod gate;
mod measurement;
mod qubit;
mod register;
mod repeat;

delegate!(Squin {
    Function,
    Return,
    Structured,
    Constant,
    Arith,
    Cmp,
    Bitwise,
    Qubit,
    Register,
    Gate,
    Measurement,
    Circuit,
    Conditional,
    Repeat,
});
