//! Define squin, a quantum circuit language with linear wires and registers.
//!
//! A `Wire` names one qubit at one point in the program. Each statement
//! consumes its input wires and returns their next values. A `Register` holds
//! an array of qubits, and `borrow` lends one of them to a wire.
#![forbid(unsafe_code)]

pub mod bits;
pub mod gate;
pub mod kernel;
pub mod language;
pub mod passes;
pub mod rewrite;
pub mod run;
pub mod state;
pub mod stim;
pub mod threads;
pub mod types;
pub mod verify;

pub use kernel::{Kernel, KernelError};
pub use language::Squin;
pub use threads::Threads;
pub use types::{Length, SquinType};
pub use verify::{Rule, Violation, verify};
