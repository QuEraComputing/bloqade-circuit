//! Give each squin statement its `ForwardEval` rule.
//!
//! Each file holds the rules of one dialect. The wrapper enums, such as
//! `Squin` and `Gate`, derive Kirin's `Interpretable`, which forwards every
//! semantic key to the statement of each variant.

mod circuit;
mod conditional;
mod gate;
mod measurement;
mod qubit;
mod register;
mod repeat;

pub use conditional::ConditionalFrame;
pub use repeat::RepeatFrame;
