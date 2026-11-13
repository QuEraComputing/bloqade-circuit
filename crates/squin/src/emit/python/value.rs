//! Hold the Python expression that stands for one SSA value.

/// Name one SSA value as a Python expression.
///
/// `number` holds the value of a numeric constant, so a rotation can fold
/// its angle from turns to radians into one literal.
#[derive(Clone, Debug, PartialEq)]
pub struct Py {
    pub text: String,
    pub number: Option<f64>,
}

impl Py {
    /// Return an expression with no known numeric value.
    pub fn expr(text: impl Into<String>) -> Self {
        Self {
            text: text.into(),
            number: None,
        }
    }
}
