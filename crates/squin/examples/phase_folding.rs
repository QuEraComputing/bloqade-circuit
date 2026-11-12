//! Merge two T gates on the control wire across a controlled-X gate.
//!
//! Controlled-X preserves its control parity, so both T gates act on the same parity.
//! Their combined phase is one S gate, which Stim can express.

use std::error::Error;

use kirin::prelude::*;
use squin::emit::stim;
use squin::ir::dialects::gate::Gate;
use squin::ir::query;
use squin::rewrite::passes::fold_phases;
use squin::{Squin, verify};

fn phase_counts(stage: &StageInfo<Squin>) -> (usize, usize) {
    let (mut t, mut s) = (0, 0);
    for function in query::functions(stage) {
        for root in query::body_blocks(stage, function) {
            for block in query::nested_blocks(stage, root) {
                for statement in block.statements(stage) {
                    match statement.definition(stage) {
                        Squin::Gate(Gate::T(_)) => t += 1,
                        Squin::Gate(Gate::S(_)) => s += 1,
                        _ => {}
                    }
                }
            }
        }
    }
    (t, s)
}

fn main() -> Result<(), Box<dyn Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(include_str!("phase_folding.kirin"))?;
    let stage = pipeline.stage_by_name("kernel").expect("The stage exists.");
    let before = pipeline.stage(stage).expect("The stage has a program.");
    verify(before).map_err(|violations| format!("{violations:?}"))?;
    assert_eq!(phase_counts(before), (2, 0));
    println!("Before phase folding:\n{}", pipeline.sprint());

    let removed = fold_phases(&mut pipeline, stage)?;
    assert_eq!(removed, 1);
    let after = pipeline.stage(stage).expect("The pass returned the stage.");
    verify(after).map_err(|violations| format!("{violations:?}"))?;
    assert_eq!(phase_counts(after), (0, 1));

    println!("After phase folding:\n{}", pipeline.sprint());
    let circuit = stim::emit(&pipeline, "kernel", "main")?;
    assert_eq!(circuit, "H 0\nH 1\nCX 0 1\nS 0\nM 0 1\n");
    println!("Stim circuit:\n{circuit}");
    Ok(())
}
