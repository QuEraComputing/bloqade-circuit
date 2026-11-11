//! Track each qubit value as a sum of path variables modulo two.

use std::collections::BTreeSet;

/// Hold a sum modulo 2 of path variables, maybe with the constant 1 added.
///
/// `variables` is sorted, so two equal sums have equal fields.
#[derive(Clone, Debug, PartialEq, Eq, Hash)]
pub(super) struct Parity {
    pub(super) variables: Vec<u32>,
    pub(super) negated: bool,
}

impl Parity {
    pub(super) fn fresh(variable: u32) -> Self {
        let variables = vec![variable];
        Parity {
            variables,
            negated: false,
        }
    }

    /// Return the parity with the constant 1 added.
    pub(super) fn flipped(&self) -> Self {
        let variables = self.variables.clone();
        Parity {
            variables,
            negated: !self.negated,
        }
    }

    /// Return the sum modulo 2 of the two parities.
    ///
    /// A variable in both parities appears twice and drops out.
    pub(super) fn plus(&self, other: &Self) -> Self {
        let left: BTreeSet<u32> = self.variables.iter().copied().collect();
        let right: BTreeSet<u32> = other.variables.iter().copied().collect();
        let variables = left.symmetric_difference(&right).copied().collect();
        let negated = self.negated != other.negated;
        Parity { variables, negated }
    }
}
