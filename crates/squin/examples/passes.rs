//! Use Kirin's pipeline and run one Squin rewrite pass explicitly.

use kirin::prelude::*;
use squin::ir::query;
use squin::rewrite::passes::cancel_gates;
use std::error::Error;

use squin::{Squin, verify};

fn main() -> Result<(), Box<dyn Error>> {
    // Squin supplies the language that this Kirin stage stores.
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(include_str!("bell.kirin"))?;
    let stage = pipeline.stage_by_name("kernel").expect("The stage exists.");
    let program = pipeline.stage(stage).expect("The stage has a program.");
    verify(program).map_err(|violations| format!("{violations:?}"))?;

    for function in query::functions(program) {
        for root in query::body_blocks(program, function) {
            for block in query::nested_blocks(program, root) {
                let statements = block.statements(program).count();
                println!("The block has {statements} statements before its terminator.");
            }
        }
    }

    println!("Before cancellation:\n{}", pipeline.sprint());
    let pairs = cancel_gates(&mut pipeline, stage)?;
    assert_eq!(pairs, 1);

    // A pass changes the program, so the caller verifies the resulting stage again.
    let program = pipeline.stage(stage).expect("The pass returned the stage.");
    verify(program).map_err(|violations| format!("{violations:?}"))?;
    println!("The number of removed inverse gate pairs is {pairs}.");
    println!("After cancellation:\n{}", pipeline.sprint());
    Ok(())
}
