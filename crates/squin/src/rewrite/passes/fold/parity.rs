//! Track each qubit value as a sum of path variables modulo two.

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
    pub(super) fn plus(&self, other: &Self) -> Self {
        let (mut left, mut right) = (
            self.variables.iter().peekable(),
            other.variables.iter().peekable(),
        );
        let mut variables = Vec::new();
        loop {
            match (left.peek(), right.peek()) {
                (Some(a), Some(b)) if a == b => {
                    left.next();
                    right.next();
                }
                (Some(a), Some(b)) if a < b => variables.extend(left.next()),
                (Some(_), Some(_)) | (None, Some(_)) => variables.extend(right.next()),
                (Some(_), None) => variables.extend(left.next()),
                (None, None) => break,
            }
        }
        let negated = self.negated != other.negated;
        Parity { variables, negated }
    }
}
