use kirin::prelude::*;
use squin::ops::{
    AllocRegister, Borrow, CX, FreeRegister, Function, H, IntConstant, Measure, Release,
};
use squin::{Circuit, Type, validate};

pub fn main() -> Result<(), Box<dyn std::error::Error>> {
    let mut builder = BuilderStageInfo::<Circuit>::default();
    let size = IntConstant::new(&mut builder, 2);
    let zero = IntConstant::new(&mut builder, 0);
    let one = IntConstant::new(&mut builder, 1);
    let register = AllocRegister::new(&mut builder, size.result);
    let q0 = Borrow::new(&mut builder, register.register, zero.result);
    let q1 = Borrow::new(&mut builder, q0.register_out, one.result);
    let h = H::new(&mut builder, q0.wire);
    let cx = CX::new(&mut builder, h.wire_out, q1.wire);
    let m0 = Measure::new(&mut builder, cx.control_out);
    let m1 = Measure::new(&mut builder, cx.target_out);
    let r0 = Release::new(&mut builder, q1.register_out, zero.result, m0.wire_out);
    let r1 = Release::new(&mut builder, r0.register_out, one.result, m1.wire_out);
    let free = FreeRegister::new(&mut builder, r1.register_out);
    let result = m0.bit;
    let body = builder
        .digraph()
        .node(size.into())
        .node(zero.into())
        .node(one.into())
        .node(register.into())
        .node(q0.into())
        .node(q1.into())
        .node(h.into())
        .node(cx.into())
        .node(m0.into())
        .node(m1.into())
        .node(r0.into())
        .node(r1.into())
        .node(free.into())
        .yield_value(result.into())
        .new();
    let signature = Signature::new(vec![], Type::Bit, ());
    let function = Function::new(&mut builder, body, signature.clone());
    let mut symbols = InternTable::<String, GlobalSymbol>::default();
    let name = symbols.intern("bell_pair".to_owned());
    let staged = builder
        .staged_function()
        .name(name)
        .signature(signature)
        .new()?;
    builder
        .specialize()
        .staged_func(staged)
        .definition(function)
        .new()?;
    let stage_name = symbols.intern("squin".to_owned());
    builder.set_name(Some(stage_name));
    let stage = builder.finalize()?;
    validate(&stage)?;
    let document = Document::with_global_symbols(Default::default(), &stage, &symbols);
    let mut rendered = String::new();
    document
        .print_staged_function(&staged)
        .render_fmt(100, &mut rendered)?;
    println!("{rendered}");
    Ok(())
}
