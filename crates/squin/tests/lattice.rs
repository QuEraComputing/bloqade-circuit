//! Check the lattice laws and the text form of the squin types.

use kirin::parsers::parse_ast;
use kirin::prelude::*;
use kirin_arith::ArithType;
use squin::{Length, Scalar, SquinType};

/// Return one value of each type shape, with known and unknown lengths.
fn samples() -> Vec<SquinType> {
    let lengths = [Length::Known(2), Length::Known(3), Length::Any];
    let mut types = vec![
        SquinType::Any,
        SquinType::Bottom,
        SquinType::Bool,
        SquinType::MeasurementResult,
        SquinType::Wire,
        SquinType::Slot,
    ];
    types.extend(
        [
            ArithType::I8,
            ArithType::I16,
            ArithType::I32,
            ArithType::I64,
            ArithType::I128,
            ArithType::U8,
            ArithType::U16,
            ArithType::U32,
            ArithType::U64,
            ArithType::U128,
            ArithType::F32,
            ArithType::F64,
        ]
        .map(SquinType::Number),
    );
    for len in lengths {
        types.push(SquinType::MeasurementResults(len));
        types.push(SquinType::Register { len, lent: 0 });
        types.push(SquinType::Register { len, lent: 1 });
    }
    types
}

#[test]
fn join_and_meet_agree_with_the_order() {
    for a in samples() {
        for b in samples() {
            assert_eq!(a.join(&b), b.join(&a), "{a} join {b}");
            assert_eq!(a.meet(&b), b.meet(&a), "{a} meet {b}");
            assert_eq!(a.is_subseteq(&b), a.join(&b) == b, "{a} below {b}");
            assert_eq!(a.is_subseteq(&b), a.meet(&b) == a, "{a} below {b}");
            assert_eq!(a.join(&a.meet(&b)), a, "{a} absorbs {b}");
            assert_eq!(a.meet(&a.join(&b)), a, "{a} absorbs {b}");
        }
    }
}

#[test]
fn join_and_meet_are_associative() {
    for a in samples() {
        for b in samples() {
            for c in samples() {
                assert_eq!(a.join(&b).join(&c), a.join(&b.join(&c)), "{a} {b} {c}");
                assert_eq!(a.meet(&b).meet(&c), a.meet(&b.meet(&c)), "{a} {b} {c}");
            }
        }
    }
}

#[test]
fn registers_with_different_lent_counts_are_unrelated() {
    let whole = SquinType::register(Length::Known(2));
    let lent = SquinType::Register {
        len: Length::Known(2),
        lent: 1,
    };
    assert_eq!(whole.join(&lent), SquinType::Any);
    assert_eq!(whole.meet(&lent), SquinType::Bottom);
}

#[test]
fn each_type_prints_to_text_that_parses_to_the_same_type() {
    for ty in samples() {
        let text = ty.to_string();
        assert_eq!(parse_ast::<SquinType>(&text).ok(), Some(ty), "{text}");
    }
}

#[test]
fn a_register_type_prints_its_lent_count_only_if_it_is_positive() {
    assert_eq!(SquinType::register(Length::Any).to_string(), "Register[?]");
    let lent = SquinType::Register {
        len: Length::Known(3),
        lent: 2,
    };
    assert_eq!(lent.to_string(), "Register[3; lent=2]");
}

#[test]
fn each_constant_prints_to_text_that_parses_to_the_same_constant() {
    let floats = [0.5, -2.0, 1e-7, 3e20, 0.1 + 0.2].map(Scalar::from);
    let others = [
        Scalar::from(-3_i64),
        Scalar::Bool(true),
        Scalar::Bool(false),
    ];
    for scalar in floats.into_iter().chain(others) {
        let text = scalar.to_string();
        assert_eq!(parse_ast::<Scalar>(&text).ok(), Some(scalar), "{text}");
    }
}
