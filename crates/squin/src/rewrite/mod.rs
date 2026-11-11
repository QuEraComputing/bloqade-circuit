//! Rewrite squin programs.
//!
//! `rules` holds the local rules and the driver that applies them to each
//! statement. `passes` runs rules and block rewrites over one pipeline stage.

pub mod passes;
pub mod rules;
