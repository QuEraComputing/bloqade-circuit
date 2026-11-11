use std::fmt;

/// Name the verifier rule that a program breaks.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Rule {
    /// A statement has an operand or a result of the wrong type.
    Type,
    /// A wire, a register or a slot has a number of uses other than one.
    SingleUse,
    /// A nested block consumes a linear value of an outer block in a way that
    /// can run a number of times other than one.
    Capture,
    /// A slot leaves the block of its `borrow`.
    SlotScope,
    /// A qubit or a register arrives at a place that belongs to another one.
    Origin,
    /// Two open borrows of one register can take the same element.
    Distinct,
}

/// Describe one place where a program breaks a verifier rule.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Violation {
    pub rule: Rule,
    pub message: String,
}

impl fmt::Display for Violation {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}: {}", self.rule, self.message)
    }
}

impl std::error::Error for Violation {}

/// Collect the violations that the rules find.
#[derive(Default)]
pub(super) struct Report {
    violations: Vec<Violation>,
}

impl Report {
    pub(super) fn add(&mut self, rule: Rule, message: String) {
        self.violations.push(Violation { rule, message });
    }

    pub(super) fn finish(self) -> Result<(), Vec<Violation>> {
        if self.violations.is_empty() {
            Ok(())
        } else {
            Err(self.violations)
        }
    }
}
