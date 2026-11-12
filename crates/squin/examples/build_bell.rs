//! Build and verify a Bell circuit with Kirin's generated operation constructors.

use kirin::prelude::*;
use kirin_function::{Function, Return};
use squin::ir::dialects::bits::BitsPack;
use squin::ir::dialects::gate::{CX, H};
use squin::ir::dialects::qubit::{Alloc, Free, Measure};
use std::error::Error;

use squin::emit::stim;
use squin::{Length, Squin, SquinType, verify};

fn main() -> Result<(), Box<dyn Error>> {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse("stage @kernel fn @main() -> Bits[2];")?;
    let stage = pipeline.stage_by_name("kernel").expect("The stage exists.");
    let function = pipeline.resolve_staged_function("main", stage).unwrap();

    pipeline.stage_mut(stage).unwrap().with_builder(|builder| {
        // The operation declarations supply the Wire and Bit result types.
        let a = Alloc::new(builder);
        let b = Alloc::new(builder);
        let h = H::new(builder, a.wire);
        let cx = CX::new(builder, h.wire_out, b.wire);
        let left = Measure::new(builder, cx.control_out);
        let right = Measure::new(builder, cx.target_out);
        let free_left = Free::new(builder, left.wire_out);
        let free_right = Free::new(builder, right.wire_out);
        let bits = BitsPack::new(builder, vec![left.bit.into(), right.bit.into()]);
        let ret = Return::<SquinType>::new(builder, vec![bits.result.into()]);

        let entry = builder
            .block()
            .stmt(a)
            .stmt(b)
            .stmt(h)
            .stmt(cx)
            .stmt(left)
            .stmt(right)
            .stmt(free_left)
            .stmt(free_right)
            .stmt(bits)
            .terminator(ret)
            .new();
        let cfg = builder.cfg().add_block(entry).new();
        let signature = Signature::new(Vec::new(), SquinType::Bits(Length::Known(2)), ());
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
