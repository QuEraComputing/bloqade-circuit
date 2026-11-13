//! Define the local gate rules as Kirin rewrite patterns.
//!
//! Each rule is a `#[rewrite_rule]` pattern that matches two gates in a row.
//! Kirin's `RewriteDriver` tries every rule at every statement until no rule
//! changes the program. After each sweep, the driver erases every pure
//! statement whose results nothing reads. Squin marks gates pure and keeps
//! `measure`, `reset` and `free` impure, so the cleanup erases matched gates
//! and never a measurement.
//!
//! A pattern only matches a gate whose operand comes from a gate in the same
//! body. A gate inside a `circuit` reads a port of that graph, so two gates
//! in different circuits never match.

mod cancel;
mod merge;

use kirin_rewrite::{PatternRule, RuleSet};
use kirin_wildcard::PatternLanguage;

use crate::ir::Squin;

/// Return the rules that remove two gates in a row whose product is the identity.
pub fn cancel_inverse() -> RuleSet<Squin> {
    build(cancel::patterns)
}

/// Return the rules that merge two rotations in a row about one axis.
pub fn merge_rotations() -> RuleSet<Squin> {
    build(merge::patterns)
}

/// Return every gate rule: the cancel rules first, then the merge rules.
pub fn gate_rules() -> RuleSet<Squin> {
    build(|stage| {
        let mut patterns = cancel::patterns(stage);
        patterns.extend(merge::patterns(stage));
        patterns
    })
}

type Stage = kirin::ir::BuilderStageInfo<PatternLanguage<Squin>>;

fn build(patterns: impl FnOnce(&mut Stage) -> Vec<PatternRule<Squin>>) -> RuleSet<Squin> {
    // The patterns are fixed Rust code, so a rejected pattern is a bug in this crate.
    RuleSet::build(patterns).expect("the squin gate rules are valid patterns")
}
