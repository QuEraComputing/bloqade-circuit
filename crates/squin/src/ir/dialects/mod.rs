//! Define the statements of each squin dialect.
//!
//! A file holds the statements of one dialect and the traits that describe
//! their shape. The type rules live in `verify::typing`, and the forward
//! rules live in `analysis::semantics`.

pub mod bits;
mod from_kirin;
pub mod gate;
pub mod qubit;
pub mod register;
