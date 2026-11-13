//! Describe the arms of the conditional.

use super::{Nesting, Structure};
use crate::ir::dialects::conditional::Conditional;

impl Structure for Conditional {
    fn nesting(&self) -> Nesting<'_> {
        Nesting::Arms {
            arms: [self.then_body, self.else_body],
            inputs: &self.inputs,
        }
    }
}
