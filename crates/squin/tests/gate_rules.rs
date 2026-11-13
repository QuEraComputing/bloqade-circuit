//! Check each Kirin rewrite pattern of the gate rules on a small kernel.

mod common;

use kirin::prelude::*;
use squin::rewrite::passes;
use squin::{Squin, verify};

/// Run `simplify` on the kernel `body`, check the result, and return the rewrite count and the text.
fn simplify(body: &str) -> (usize, String) {
    let mut pipeline = common::kernel("", body);
    let stage = pipeline.stage_by_name("kernel").expect("the stage exists");
    assert!(verify(pipeline.stage(stage).unwrap()).is_ok());
    let rewrites = passes::simplify(&mut pipeline, stage).expect("the pass succeeds");
    let rewritten: &StageInfo<Squin> = pipeline.stage(stage).unwrap();
    if let Err(violations) = verify(rewritten) {
        panic!("{violations:?}\n{}", pipeline.sprint());
    }
    (rewrites, pipeline.sprint())
}

/// Return a kernel that applies `first` and then `second` to one qubit and measures it.
fn one_qubit(first: &str, second: &str) -> String {
    format!(
        "%a0 = alloc;
         %a1, %m = circuit %a0 digraph ^g(%a: Wire) {{
           %a2 = {first} %a;
           %a3 = {second} %a2;
           %a4, %r = measure %a3;
           yield %a4, %r;
         }} -> Wire, MeasurementResult;
         free %a1;
         %n = constant 0 -> Int;
         ret %n;"
    )
}

#[test]
fn every_one_qubit_inverse_pair_cancels() {
    let pairs = [
        ("x", "x"),
        ("y", "y"),
        ("z", "z"),
        ("h", "h"),
        ("s", "s_dag"),
        ("s_dag", "s"),
        ("t", "t_dag"),
        ("t_dag", "t"),
        ("sqrt_x", "sqrt_x_dag"),
        ("sqrt_x_dag", "sqrt_x"),
        ("sqrt_y", "sqrt_y_dag"),
        ("sqrt_y_dag", "sqrt_y"),
    ];
    for (first, second) in pairs {
        let (rewrites, text) = simplify(&one_qubit(first, second));
        assert_eq!(rewrites, 1, "{first} {second}\n{text}");
        assert!(!text.contains(&format!("= {first} ")), "{text}");
        // Nothing reads the measurement result, and the cleanup still keeps `measure`.
        assert!(text.contains("measure %a;"), "{text}");
    }
}

#[test]
fn every_self_inverse_two_qubit_gate_cancels() {
    for gate in ["cx", "cy", "cz"] {
        let body = format!(
            "%c0 = alloc;
             %t0 = alloc;
             %c1, %t1 = circuit %c0, %t0 digraph ^g(%c: Wire, %t: Wire) {{
               %c2, %t2 = {gate} %c, %t;
               %c3, %t3 = {gate} %c2, %t2;
               yield %c3, %t3;
             }} -> Wire, Wire;
             free %c1;
             free %t1;
             %n = constant 0 -> Int;
             ret %n;"
        );
        let (rewrites, text) = simplify(&body);
        assert_eq!(rewrites, 1, "{gate}\n{text}");
        assert!(text.contains("yield %c, %t;"), "{text}");
    }
}

#[test]
fn a_gate_and_a_different_gate_stay() {
    let (rewrites, text) = simplify(&one_qubit("s", "s"));
    assert_eq!(rewrites, 0, "{text}");
}

#[test]
fn two_rotations_about_x_or_y_merge() {
    for axis in ["rx", "ry"] {
        let body = format!(
            "%x = constant 0.25 -> Float;
             %a0 = alloc;
             %a1 = circuit %a0, %x digraph ^g(%a: Wire) capture(%x: Float) {{
               %a2 = {axis}(%x) %a;
               %a3 = {axis}(%x) %a2;
               yield %a3;
             }} -> Wire;
             free %a1;
             %n = constant 0 -> Int;
             ret %n;"
        );
        let (rewrites, text) = simplify(&body);
        assert_eq!(rewrites, 1, "{axis}\n{text}");
        assert_eq!(text.matches(&format!("= {axis} ")).count(), 1, "{text}");
        assert_eq!(text.matches(" add ").count(), 1, "{text}");
    }
}

#[test]
fn rotations_about_different_axes_stay() {
    let body = "%x = constant 0.25 -> Float;
                %a0 = alloc;
                %a1 = circuit %a0, %x digraph ^g(%a: Wire) capture(%x: Float) {
                  %a2 = rx(%x) %a;
                  %a3 = rz(%x) %a2;
                  yield %a3;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    let (rewrites, text) = simplify(body);
    assert_eq!(rewrites, 0, "{text}");
}
