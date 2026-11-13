//! Build and verify a Bell circuit with Kirin's generated operation constructors.
//!
//! The gates sit in the graph of a `circuit` region, and the region sits in
//! the entry block.

use kirin::prelude::*;
use kirin_function::{Function, Return};
use squin::ir::dialects::circuit::Circuit;
use squin::ir::dialects::gate::{CX, H};
use squin::ir::dialects::measurement::PackResults;
use squin::ir::dialects::qubit::{Alloc, Free, Measure};
use std::error::Error;

use squin::emit::stim;
use squin::{Length, Squin, SquinType, verify};

fn main() -> Result<(), Box<dyn Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse("stage @kernel fn @main() -> MeasurementResults[2];")?;
    let stage = pipeline.stage_by_name("kernel").expect("The stage exists.");
    let function = pipeline.resolve_staged_function("main", stage).unwrap();

    pipeline.stage_mut(stage).unwrap().with_builder(|builder| {
        // The operation declarations supply the Wire and MeasurementResult result types.
        let a = Alloc::new(builder);
        let b = Alloc::new(builder);

        // The gates read port placeholders, which the graph builder resolves.
        let left_port = builder.graph_port().index(0);
        let right_port = builder.graph_port().index(1);
        let h = H::new(builder, left_port);
        let cx = CX::new(builder, h.wire_out, right_port);
        let left = Measure::new(builder, cx.control_out);
        let right = Measure::new(builder, cx.target_out);
        let graph = builder
            .digraph()
            .port(SquinType::Wire)
            .port(SquinType::Wire)
            .node(h.id)
            .node(cx.id)
            .node(left.id)
            .node(right.id)
            .yield_value(left.wire_out.into())
            .yield_value(right.wire_out.into())
            .yield_value(left.result.into())
            .yield_value(right.result.into())
            .new();
        let types = [
            SquinType::Wire,
            SquinType::Wire,
            SquinType::MeasurementResult,
            SquinType::MeasurementResult,
        ];
        let inputs = vec![a.wire.into(), b.wire.into()];
        let (region, results) = Circuit::build(builder, inputs, graph, &types);

        let free_left = Free::new(builder, results[0]);
        let free_right = Free::new(builder, results[1]);
        let packed = PackResults::new(builder, vec![results[2].into(), results[3].into()]);
        let ret = Return::<SquinType>::new(builder, vec![packed.packed.into()]);

        let entry = builder
            .block()
            .stmt(a)
            .stmt(b)
            .stmt(region)
            .stmt(free_left)
            .stmt(free_right)
            .stmt(packed)
            .terminator(ret)
            .new();
        let cfg = builder.cfg().add_block(entry).new();
        let signature = Signature::new(
            Vec::new(),
            SquinType::MeasurementResults(Length::Known(2)),
            (),
        );
        let definition = Function::<SquinType>::new(builder, cfg, signature);
        builder
            .specialize()
            .staged_func(function)
            .definition(definition)
            .new()
            .unwrap();
    });

    if let Err(violations) = verify(pipeline.stage(stage).unwrap()) {
        return Err(format!("{violations:?}").into());
    }
    println!("The builders produced:\n{}", pipeline.sprint());
    let circuit = stim::emit(&pipeline, "kernel", "main")?;
    assert_eq!(circuit, "H 0\nCX 0 1\nM 0\nM 1\n");
    println!("Stim circuit:\n{circuit}");
    Ok(())
}
