//! Verify and transform Squin programs.
//!
//! The verifier checks types and ownership before execution.
//! Rewrite rules edit statements, and passes apply those rules to a pipeline stage.

pub mod passes;
pub mod rewrite;
pub mod verify;
