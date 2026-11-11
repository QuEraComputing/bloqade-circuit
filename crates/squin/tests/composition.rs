//! Check that another language can wrap the squin dialects with its own type lattice.

use kirin::prelude::*;
use kirin_function::{Function, Return};
use squin::Threads;
use squin::ir::dialects::{gate, qubit};
use squin::ir::types::{Length, QuantumTypes};

/// Name the types of a small language that knows only qubits and bits.
#[derive(Clone, Copy, Debug, Hash, PartialEq, Eq, HasParser, PrettyPrint)]
enum Tiny {
    #[chumsky(format = "Qubit")]
    Qubit,
    #[chumsky(format = "Bit")]
    Bit,
    #[chumsky(format = "Other")]
    Other,
}

impl Placeholder for Tiny {
    fn placeholder() -> Self {
        Tiny::Other
    }
}

impl QuantumTypes for Tiny {
    fn wire() -> Self {
        Tiny::Qubit
    }

    fn slot() -> Self {
        Tiny::Other
    }

    fn bit() -> Self {
        Tiny::Bit
    }

    fn bits(_length: Length) -> Self {
        Tiny::Other
    }

    fn register(_length: Length) -> Self {
        Tiny::Other
    }

    fn index() -> Self {
        Tiny::Other
    }
}

/// Combine the squin gate and qubit dialects with Kirin functions over `Tiny`.
#[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
#[kirin(builders, type = Tiny)]
enum TinyLanguage {
    #[wraps]
    Function(Function<Tiny>),
    #[wraps]
    Return(Return<Tiny>),
    #[wraps(lift_project_from(
        qubit::Alloc<Tiny>,
        qubit::Free<Tiny>,
        qubit::Measure<Tiny>,
        qubit::Reset<Tiny>
    ))]
    Qubit(qubit::QubitOp<Tiny>),
    #[wraps]
    Gate(gate::Gate<Tiny>),
}

const PROGRAM: &str = "stage @tiny fn @main() -> Bit;
specialize @tiny fn @main() -> Bit cfg {
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
fn another_language_parses_and_prints_the_squin_statements_with_its_own_types() {
    let mut pipeline: Pipeline<StageInfo<TinyLanguage>> = Pipeline::new();
    pipeline.parse(PROGRAM).expect("the program parses");
    let printed = pipeline.sprint();
    assert!(printed.contains("%a1 = h %a0;"), "{printed}");
    assert!(printed.contains("measure %a1;"), "{printed}");
    let mut reparsed: Pipeline<StageInfo<TinyLanguage>> = Pipeline::new();
    reparsed.parse(&printed).expect("the printed text parses");
    assert_eq!(printed, reparsed.sprint());
}

#[test]
fn the_builders_give_the_fixed_result_types_of_the_other_lattice() {
    let mut stage: StageInfo<TinyLanguage> = StageInfo::default();
    let (wire, result) = stage.with_builder(|builder| {
        let alloc = qubit::Alloc::<Tiny>::new(builder);
        let measure = qubit::Measure::<Tiny>::new(builder, alloc.wire);
        (measure.wire_out, measure.bit)
    });
    let ty = |value: ResultValue| *SSAValue::from(value).expect_info(&stage).ty();
    assert_eq!((ty(wire), ty(result)), (Tiny::Qubit, Tiny::Bit));
}

#[test]
fn the_shape_traits_work_for_every_type_lattice() {
    let (wire, wire_out) = (SSAValue::from(TestSSAValue(0)), TestSSAValue(1));
    let h = gate::H::<Tiny> {
        wire,
        wire_out: SSAValue::from(wire_out).into(),
        marker: std::marker::PhantomData,
    };
    assert_eq!(h.threads().len(), 1);
}
