#![forbid(unsafe_code)]

pub mod language;
pub mod ops;
pub mod passes;
pub mod rewrite;
pub mod stage;
pub mod types;
pub mod validation;

pub use language::Circuit;
pub use ops::Squin;
pub use passes::{RzStats, optimize_rz};
pub use stage::Stage;
pub use types::{RegisterLength, Type};
pub use validation::{ValidationError, validate};
