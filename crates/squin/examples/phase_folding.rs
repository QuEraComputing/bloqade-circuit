//! Merge two T gates on the control wire across a controlled-X gate.
//!
//! Controlled-X preserves its control parity, so both T gates act on the same parity.
//! Their combined phase is one S gate, which the Stim backend can emit.

use kirin::prelude::*;
use squin::ir::ops::Gate;
use squin::ir::query;
use squin::rewrite::passes::fold_phases;
use squin::{Kernel, KernelError, Squin, verify};

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

fn main() -> Result<(), KernelError> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline
        .parse(include_str!("phase_folding.kirin"))
        .map_err(KernelError::Parse)?;
    let stage = pipeline.stage_by_name("kernel").expect("The stage exists.");
    let before = pipeline.stage(stage).expect("The stage has a program.");
    verify(before).map_err(KernelError::Invalid)?;
    assert_eq!(phase_counts(before), (2, 0));
    println!("Before phase folding:\n{}", pipeline.sprint());

    let removed = fold_phases(&mut pipeline, stage).map_err(KernelError::Pass)?;
    assert_eq!(removed, 1);
    let after = pipeline.stage(stage).expect("The pass returned the stage.");
    verify(after).map_err(KernelError::Invalid)?;
    assert_eq!(phase_counts(after), (0, 1));

    let optimized = pipeline.sprint();
    println!("After phase folding:\n{optimized}");
    let circuit = Kernel::parse(&optimized)?.to_stim("main")?;
    assert_eq!(circuit, "H 0\nH 1\nCX 0 1\nS 0\nM 0 1\n");
    println!("Stim circuit:\n{circuit}");
    Ok(())
}
