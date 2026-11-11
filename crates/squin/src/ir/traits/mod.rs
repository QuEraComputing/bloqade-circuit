//! Define the traits that every statement implements.
//!
//! The verifier, the rewrite passes and the runtime ask a statement about
//! itself only through these traits. A new statement brings its own answers.

mod execute;
pub(crate) mod macros;
mod structure;
mod threads;
mod typed;

pub use execute::Execute;
pub use structure::{Lending, Nesting, Offset, Structure};
pub use threads::{Pairs, Threads};
pub use typed::Typed;
