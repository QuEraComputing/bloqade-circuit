//! Define squin, a quantum circuit language with linear wires and registers.
//!
//! A `Wire` names one qubit at one point in the program. Each statement
//! consumes its input wires and returns their next values. A `Register` holds
//! an array of qubits, and `borrow` lends one of them to a wire.
//!
//! `ir` defines and queries programs. `verify` and `rewrite` depend on `ir`.
//! `runtime` depends on `ir` and the verifier's `Verified` value.
//! Each layer owns its statement traits and their implementations.
//! `kernel` connects parsing, verification, optimization, and execution.
#![forbid(unsafe_code)]

pub mod ir;
pub mod kernel;
pub mod rewrite;
pub mod runtime;
pub mod verify;

pub use ir::Squin;
pub use ir::traits::{Pairs, Threads};
pub use ir::types::{ArithType, ArithValue, Length, Scalar, SquinType};
pub use kernel::{Kernel, KernelError};
pub use verify::{Rule, Verified, Violation, verify};
