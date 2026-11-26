use kirin::prelude::*;
use squin::{Circuit, RzStats, Type, ops::Rz, optimize_rz};

#[derive(Clone, Debug, PartialEq, Dialect, HasParser)]
#[kirin(type = Type)]
enum Mixed {
    #[wraps(lift_project_from(Rz))]
    Circuit(Circuit),
}

#[derive(StageMeta, ParseDispatch)]
enum MixedStage {
    #[stage(name = "mixed")]
    Mixed(StageInfo<Mixed>),
}

#[test]
fn the_pass_accepts_a_composed_language_and_all_its_functions() {
    let mut pipeline = Pipeline::<MixedStage>::new();
    pipeline
        .parse(
            "stage @mixed fn @first(Wire) -> Wire;
        specialize @mixed fn @first(Wire) -> Wire digraph ^first(%q: Wire) {
            %a = rz(0.25) %q -> Wire; %b = rz(-0.25) %a -> Wire; yield %b;
        }
        stage @mixed fn @second() -> Int;
        specialize @mixed fn @second() -> Int digraph ^second() {
            %n = constant 1 -> Int; %zero = constant 0 -> Int;
            %reg = alloc_register %n -> Register<1>;
            %reg1, %q = borrow %reg, %zero -> Register<1>, Wire;
            %a = rz(0.25) %q -> Wire; %b = rz(0.75) %a -> Wire;
            %reg2 = release %reg1, %zero, %b -> Register<1>;
            free_register %reg2; yield %n;
        }",
        )
        .unwrap();
    let id = pipeline.stage_by_name("mixed").unwrap();
    assert_eq!(
        optimize_rz::<Mixed, _>(&mut pipeline, id).unwrap(),
        RzStats {
            removed_zero: 1,
            merged: 2
        }
    );
    let MixedStage::Mixed(stage) = pipeline.stage(id).unwrap();
    verify_derived(stage).unwrap();
    assert_eq!(
        optimize_rz::<Mixed, _>(&mut pipeline, id).unwrap(),
        RzStats::default()
    );
}
