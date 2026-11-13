use std::fmt;

/// Hold the number of elements of a register or of a `MeasurementResults` value.
///
/// `Known(3)` prints as `3`. `Any` prints as `?` and stands for a length that
/// the program fixes at run time.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq)]
pub enum Length {
    /// The length is `n` in every execution.
    Known(u64),
    /// The length can differ from one execution to the next.
    Any,
}

impl Length {
    /// Check whether every length that `self` allows is also a length of `other`.
    pub fn is_subseteq(self, other: Self) -> bool {
        self == other || other == Length::Any
    }

    /// Return the smallest length that allows both `self` and `other`.
    pub fn join(self, other: Self) -> Self {
        if self == other { self } else { Length::Any }
    }

    /// Return the largest length that both `self` and `other` allow.
    ///
    /// The result is `None` if two known lengths differ.
    pub fn meet(self, other: Self) -> Option<Self> {
        match (self, other) {
            (Length::Any, length) | (length, Length::Any) => Some(length),
            (left, right) if left == right => Some(left),
            _ => None,
        }
    }
}

impl fmt::Display for Length {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Length::Known(length) => write!(f, "{length}"),
            Length::Any => write!(f, "?"),
        }
    }
}
