//! Define squin, a quantum circuit language with linear wires and registers.
//!
//! A `Wire` names one qubit at one point in the program. Each statement
//! consumes its input wires and returns their next values. A `Register` holds
//! an array of qubits, and `borrow` lends one of them to a wire.
//!
//! `ir` defines the program. `verify`, `rewrite` and `runtime` each own the
//! trait that they ask the statements, and import only `ir` and each other
//! in that order. `kernel` ties them together.
#![forbid(unsafe_code)]

pub mod ir;
pub mod kernel;
pub mod rewrite;
pub mod runtime;
pub mod verify;

pub use ir::Squin;
pub use ir::traits::{Pairs, Threads};
pub use ir::types::{Length, Scalar, SquinType};
pub use kernel::{Kernel, KernelError};
pub use verify::{Rule, Verified, Violation, verify};
