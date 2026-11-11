//! Define squin, a quantum circuit language with linear wires and registers.
//!
//! A `Wire` names one qubit at one point in the program. Each statement
//! consumes its input wires and returns their next values. A `Register` holds
//! an array of qubits, and `borrow` lends one of them to a wire.
#![forbid(unsafe_code)]

pub mod compiler;
pub mod dialect;
pub mod kernel;
pub mod runtime;

pub use compiler::verify::{Rule, Verified, Violation, verify};
pub use dialect::Squin;
pub use dialect::traits::{Pairs, Threads};
pub use dialect::types::{Length, Scalar, SquinType};
pub use kernel::{Kernel, KernelError};
