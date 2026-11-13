//! Check that another language can wrap the squin dialects.
//!
//! The language holds only Kirin functions and the squin qubit and gate
//! dialects. It must use `SquinType`, because every statement of one Kirin
//! language shares one type.

use kirin::prelude::*;
use kirin_function::{Function, Return};
use squin::ir::dialects::{gate, qubit};
use squin::{SquinType, Threads};

/// Combine the squin gate and qubit dialects with Kirin functions.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = SquinType)]
enum SmallLanguage {
    #[wraps]
    Function(Function<SquinType>),
    #[wraps]
    Return(Return<SquinType>),
    #[wraps(lift_project_from(qubit::Alloc, qubit::Free, qubit::Measure, qubit::Reset))]
    Qubit(qubit::QubitOp),
    #[wraps]
    Gate(gate::Gate),
}

const PROGRAM: &str = "stage @small fn @main() -> MeasurementResult;
specialize @small fn @main() -> MeasurementResult cfg {
  ^entry() {
    %a0 = alloc;
    %a1 = h %a0;
    %a2, %bit = measure %a1;
    free %a2;
    ret %bit;
  }
}
";

#[test]
fn another_language_parses_and_prints_the_squin_statements() {
    let mut pipeline: Pipeline<StageInfo<SmallLanguage>> = Pipeline::new();
    pipeline.parse(PROGRAM).expect("the program parses");
    let printed = pipeline.sprint();
    assert!(printed.contains("%a1 = h %a0;"), "{printed}");
    assert!(printed.contains("measure %a1;"), "{printed}");
    let mut reparsed: Pipeline<StageInfo<SmallLanguage>> = Pipeline::new();
    reparsed.parse(&printed).expect("the printed text parses");
    assert_eq!(printed, reparsed.sprint());
}

#[test]
fn the_builders_give_the_fixed_result_types() {
    let mut stage: StageInfo<SmallLanguage> = StageInfo::default();
    let (wire, result) = stage.with_builder(|builder| {
        let alloc = qubit::Alloc::new(builder);
        let measure = qubit::Measure::new(builder, alloc.wire);
        (measure.wire_out, measure.result)
    });
    let ty = |value: ResultValue| *SSAValue::from(value).expect_info(&stage).ty();
    assert_eq!(
        (ty(wire), ty(result)),
        (SquinType::Wire, SquinType::MeasurementResult)
    );
}

#[test]
fn the_shape_traits_work_on_the_wrapped_statements() {
    let (wire, wire_out) = (SSAValue::from(TestSSAValue(0)), TestSSAValue(1));
    let h = gate::H {
        wire,
        wire_out: SSAValue::from(wire_out).into(),
    };
    assert_eq!(h.threads().len(), 1);
}
