use std::fmt;

use kirin::prelude::{Block, DiGraph, SSAValue};

use crate::ir::types::SquinType;

/// Name the verifier rule that a program breaks.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
#[non_exhaustive]
pub enum Rule {
    /// An operand uses a value outside its scope or before its definition.
    Scope,
    /// A block has a terminator that its owner cannot execute.
    Terminator,
    /// A statement has an operand or a result of the wrong type.
    Type,
    /// A wire, a register or a slot has a number of uses other than one.
    SingleUse,
    /// A nested block reads a linear value of an outer block. A linear value
    /// enters an arm only as an input of a `conditional`, and it enters a loop
    /// body only as a carried value.
    Capture,
    /// A slot leaves the block of its `borrow`.
    SlotScope,
    /// A qubit or a register arrives at a place that belongs to another one.
    Origin,
    /// Two open borrows of one register can take the same element.
    Distinct,
    /// A gate sits in a block, or control flow sits in the graph of a `circuit`.
    Placement,
}

/// Hold an SSA value with its name in the program text, such as `%r1`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Named {
    pub value: SSAValue,
    pub name: String,
}

impl fmt::Display for Named {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{}", self.name)
    }
}

/// Describe one place where a program breaks a verifier rule.
#[derive(Clone, Debug, PartialEq, Eq, thiserror::Error)]
#[non_exhaustive]
pub enum Violation {
    #[error("{value} has no visible definition before this use.")]
    OutOfScope { value: Named },
    #[error("The block {block} must end with {expected}.")]
    Terminator {
        block: Block,
        expected: &'static str,
    },
    #[error("{value} has the type {found}, and its statement needs {expected}.")]
    Type {
        value: Named,
        found: SquinType,
        expected: String,
    },
    #[error("A block passes on {found} values where {expected} must arrive.")]
    Arity { expected: usize, found: usize },
    #[error("{value} has the linear type {ty} and {uses} uses.")]
    Uses {
        value: Named,
        ty: SquinType,
        uses: usize,
    },
    #[error(
        "An arm reads the linear value {value} from an outer block. Pass it as an input of a `conditional`."
    )]
    ArmCapture { value: Named },
    #[error("{value} enters a loop body from outside the loop.")]
    LoopCapture { value: Named },
    #[error("{slot} is a slot that leaves the block of its `borrow`.")]
    SlotEscapes { slot: Named },
    #[error("{wire} fills {slot}, and it carries another qubit.")]
    WrongQubit { wire: Named, slot: Named },
    #[error("{slot} names an element of another register than {register}.")]
    WrongRegister { slot: Named, register: Named },
    #[error("A loop body moves {value} to another position of its yield.")]
    LoopMoves { value: Named },
    #[error("The borrows at {first} and {second} of one register can take the same element.")]
    SameElement { first: Named, second: Named },
    #[error("The verifier cannot find the indices of every open borrow of {register}.")]
    UnknownBorrows { register: Named },
    #[error(
        "A `circuit` graph reads {value} from an outer block. Declare it in the `capture(...)` list of the graph and pass it as an input."
    )]
    OuterRead { value: Named },
    #[error(
        "The capture {value} of a `circuit` graph has the linear type {ty}. Pass it as a port of the graph."
    )]
    LinearCapture { value: Named, ty: SquinType },
    #[error("The graph {graph} has a cycle, so its nodes have no order to run in.")]
    GraphCycle { graph: DiGraph },
    #[error("{site} must sit in {expected}.")]
    Misplaced {
        site: String,
        expected: &'static str,
    },
}

impl Violation {
    /// Return the rule that the program breaks.
    pub fn rule(&self) -> Rule {
        match self {
            Violation::OutOfScope { .. } | Violation::GraphCycle { .. } => Rule::Scope,
            Violation::Terminator { .. } => Rule::Terminator,
            Violation::Type { .. } | Violation::Arity { .. } => Rule::Type,
            Violation::Uses { .. } => Rule::SingleUse,
            Violation::ArmCapture { .. }
            | Violation::LoopCapture { .. }
            | Violation::OuterRead { .. }
            | Violation::LinearCapture { .. } => Rule::Capture,
            Violation::SlotEscapes { .. } => Rule::SlotScope,
            Violation::WrongQubit { .. }
            | Violation::WrongRegister { .. }
            | Violation::LoopMoves { .. } => Rule::Origin,
            Violation::SameElement { .. } | Violation::UnknownBorrows { .. } => Rule::Distinct,
            Violation::Misplaced { .. } => Rule::Placement,
        }
    }
}

/// Collect the violations that the rules find.
#[derive(Default)]
pub(super) struct Report {
    violations: Vec<Violation>,
}

impl Report {
    pub(super) fn add(&mut self, violation: Violation) {
        self.violations.push(violation);
    }

    pub(super) fn finish(self) -> Result<(), Vec<Violation>> {
        if self.violations.is_empty() {
            Ok(())
        } else {
            Err(self.violations)
        }
    }
}
