//! Run the address analysis and print the qubit that each value holds.
//!
//! A qubit prints as the value that allocates it, such as `%r0[2]` for the
//! third element of the register `%r0`.

use std::error::Error;

use kirin::prelude::*;
use squin::analysis::address::{self, Address, QubitId};
use squin::ir::query;
use squin::{Squin, SquinType, verify};

fn main() -> Result<(), Box<dyn Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(include_str!("address.kirin"))?;
    let stage = pipeline
        .stage_by_name("kernel")
        .ok_or("The program has no @kernel stage.")?;
    let program = pipeline.stage(stage).ok_or("The stage does not exist.")?;
    if let Err(violations) = verify(program) {
        return Err(format!("{violations:?}").into());
    }

    let addresses = address::analyze(&pipeline, "kernel", "main")?;
    for block in query::body_blocks(program, addresses.definition()) {
        for statement in block.statements(program) {
            for result in statement.results(program) {
                let value: SSAValue = (*result).into();
                let fact = show(program, &addresses.of(value));
                println!("{:>7}  {fact}", query::name(program, value));
            }
        }
    }
    Ok(())
}

/// Write `fact` with each qubit named by the value that allocates it.
fn show(program: &StageInfo<Squin>, fact: &Address) -> String {
    match fact {
        Address::Wire(qubit) => qubit_name(program, *qubit),
        Address::Register(qubits) => {
            let names: Vec<String> = qubits.iter().map(|q| qubit_name(program, *q)).collect();
            format!("[{}]", names.join(", "))
        }
        other => format!("{other:?}"),
    }
}

/// Name `qubit` as `%q` for an `alloc`, or `%r[k]` for element `k` of an `alloc_register`.
fn qubit_name(program: &StageInfo<Squin>, qubit: QubitId) -> String {
    let Some(result) = qubit.site.results(program).next() else {
        return format!("{qubit:?}");
    };
    let site: SSAValue = (*result).into();
    let name = query::name(program, site);
    match site.expect_info(program).ty() {
        SquinType::Register { .. } => format!("{name}[{}]", qubit.offset),
        _ => name,
    }
}
