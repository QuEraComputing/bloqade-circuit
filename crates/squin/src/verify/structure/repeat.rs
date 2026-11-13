//! Describe the body of the repeat loop.

use super::{Nesting, Structure};
use crate::ir::dialects::repeat::Repeat;

impl Structure for Repeat {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Loop {
            body: self.body,
            initial: &self.inputs,
            leading_arguments: 0,
            leading_yields: 1,
        }
    }
}
