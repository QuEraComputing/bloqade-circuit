//! Define what a squin program is made of.
//!
//! `types` holds the type lattice. `dialects` holds the statements. `traits`
//! holds the traits that describe the shape of a statement. `Squin` combines
//! the dialects with the Kirin statements into one language.

pub mod dialects;
mod language;
pub(crate) mod macros;
pub mod query;
pub mod traits;
pub mod types;

pub use language::Squin;
