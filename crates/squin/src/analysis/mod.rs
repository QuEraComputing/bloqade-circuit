//! Analyze squin programs with Kirin's forward interpreter.
//!
//! `semantics` gives each squin statement its `ForwardEval` rule. The rules are
//! generic over the value domain through `QuantumValue`, as Kirin's own rules
//! are generic over theirs, so one rule serves every forward engine. Kirin's
//! dialects supply the rules for constants, arithmetic, comparisons, branches,
//! loops and functions.
//!
//! `address` is one such domain: it names the qubit that each wire carries.

pub mod address;
mod semantics;
mod value;

pub use semantics::{ConditionalFrame, RepeatFrame};
pub use value::QuantumValue;
