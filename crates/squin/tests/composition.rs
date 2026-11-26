use kirin::prelude::*;
use kirin_interpreter::{ForwardEval, Interpretable, SparseForwardEffect, SparseForwardInterp};
use squin::{Circuit, Type, ValidationError, validate, validation::Value};

#[derive(
    Clone, Debug, PartialEq, Dialect, HasParser, PrettyPrint, serde::Serialize, serde::Deserialize,
)]
#[kirin(type = Type)]
#[chumsky(format = "$identity_int {input} -> {output:type}")]
struct IdentityInt {
    input: SSAValue,
    output: ResultValue,
}

impl<I> Interpretable<I, ForwardEval> for IdentityInt
where
    I: SparseForwardInterp<Value = Value, Error = ValidationError>,
{
    fn interpret(&self, interp: &mut I) -> Result<I::Effect, I::Error> {
        let value = interp.read(self.input)?;
        if !matches!(value, Value::Int(_)) {
            return Err(ValidationError::new("The identity operation requires Int."));
        }
        interp.write(self.output, value)?;
        Ok(SparseForwardEffect::Next)
    }
}

#[derive(
    Clone,
    Debug,
    PartialEq,
    Dialect,
    HasParser,
    PrettyPrint,
    Interpretable,
    serde::Serialize,
    serde::Deserialize,
)]
#[kirin(type = Type)]
enum Mixed {
    #[wraps]
    Circuit(Circuit),
    #[wraps]
    Identity(IdentityInt),
}

#[derive(StageMeta, ParseDispatch, RenderDispatch, serde::Serialize, serde::Deserialize)]
enum MixedStage {
    #[stage(name = "mixed")]
    Mixed(StageInfo<Mixed>),
}

fn parse(text: &str) -> Pipeline<MixedStage> {
    let mut pipeline = Pipeline::new();
    pipeline.parse(text).unwrap();
    pipeline
}

const PROGRAM: &str = "
stage @mixed fn @test() -> Unit;
specialize @mixed fn @test() -> Unit digraph ^circuit() {
    %n = constant 1 -> Int;
    %size = identity_int %n -> Int;
    %zero = constant 0 -> Int;
    %r = alloc_register %size -> Register<?>;
    %r1, %q = borrow %r, %zero -> Register<?>, Wire;
    %q1 = rz(0.5) %q -> Wire;
    %r2 = release %r1, %zero, %q1 -> Register<?>;
    free_register %r2;
    yield;
}";

#[test]
fn other_dialects_supply_facts_through_kirins_interpreter_interface() {
    let pipeline = parse(PROGRAM);
    let text = pipeline.sprint();
    for pipeline in [
        pipeline,
        parse(&text),
        serde_json::from_str::<Pipeline<MixedStage>>(
            &serde_json::to_string(&parse(PROGRAM)).unwrap(),
        )
        .unwrap(),
    ] {
        for MixedStage::Mixed(stage) in pipeline.stages() {
            validate(stage).unwrap();
        }
        assert_eq!(text, pipeline.sprint());
    }
}

#[test]
fn other_dialect_results_must_match_their_declared_types() {
    for MixedStage::Mixed(stage) in
        parse(&PROGRAM.replace("identity_int %n -> Int", "identity_int %n -> Bit")).stages()
    {
        assert!(
            validate(stage)
                .unwrap_err()
                .message
                .contains("requires Int")
        );
    }
}

#[test]
fn unknown_indices_remain_unknown_across_dialects() {
    let text = "stage @mixed fn @test(Int) -> Unit;
    specialize @mixed fn @test(Int) -> Unit digraph ^circuit(%i: Int) {
        %n = constant 1 -> Int;
        %index = identity_int %i -> Int;
        %r = alloc_register %n -> Register<?>;
        %r1, %q = borrow %r, %index -> Register<?>, Wire;
        free %q;
        free_register %r1;
        yield;
    }";
    for MixedStage::Mixed(stage) in parse(text).stages() {
        assert!(
            validate(stage)
                .unwrap_err()
                .message
                .contains("cannot prove the index")
        );
    }
}
