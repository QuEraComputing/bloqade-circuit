//! Check that the printer and the parser of squin agree.

mod common;

use kirin::prelude::*;
use squin::Squin;

const EVERY_STATEMENT: &str = "
    %n = constant 3 -> Int;
    %i = constant 0 -> Int;
    %half = constant 0.5 -> Float;
    %tiny = constant 1.0e-7 -> f64;
    %flag = constant true -> Bool;
    %next = add %i, %n -> Int;
    %turn = mul %angle, %half -> Float;
    %less = lt %i, %n -> Bool;
    %same = eq %flag, %less -> Bool;
    %r0 = alloc_register %n -> Register[3];
    %r1, %s, %a0 = borrow %r0, %i -> Register[3; lent=1];
    %a3 = circuit %a0 digraph ^g0(%a0: Wire) {
      %a1 = h %a0;
      %a2 = rz(%angle) %a1;
      %a3 = u3(%angle, %angle, %angle) %a2;
      yield %a3;
    } -> Wire;
    %b0 = alloc;
    %a4, %bit, %b3 = circuit %a3, %b0 digraph ^g1(%a3: Wire, %b0: Wire) {
      %a4, %b1 = cx %a3, %b0;
      %b2, %bit = measure %b1;
      %b3 = reset %b2;
      yield %a4, %bit, %b3;
    } -> Wire, MeasurementResult, Wire;
    %r2 = release %r1, %s, %a4 -> Register[3];
    %r3, %b4 = replace %r2, %i, %b3 -> Register[3];
    %r4, %size = length %r3 -> Register[3];
    %front, %back = split %r4, %i -> Register[?], Register[?];
    %r5 = join %front, %back -> Register[?];
    %r6, %bits = measure_register %r5 -> Register[?], MeasurementResults[?];
    %first = get_result %bits, %i;
    %pair = pack_results %bit, %first -> MeasurementResults[2];
    %count = results_length %pair;
    %single = pack %b4 -> Register[1];
    free_register %single;
    free_register %r6;
    ret %count;";

#[test]
fn the_printer_gives_text_that_parses_to_the_same_program() {
    let printed = common::kernel("%angle: Float", EVERY_STATEMENT).sprint();
    let mut reparsed: Pipeline<StageInfo<Squin>> = Pipeline::new();
    reparsed.parse(&printed).expect("the printed text parses");
    assert_eq!(printed, reparsed.sprint());
}

#[test]
fn the_printer_keeps_the_lent_count_of_a_register_type() {
    let printed = common::kernel("%angle: Float", EVERY_STATEMENT).sprint();
    assert!(printed.contains("-> Register[3; lent=1];"), "{printed}");
    assert!(printed.contains("constant 1.0e-7 -> f64;"), "{printed}");
    assert!(printed.contains("%a4, %b1 = cx %a3, %b0;"), "{printed}");
}
