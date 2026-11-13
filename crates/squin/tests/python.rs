//! Check the Python squin text that the Python emitter writes.

mod common;

use kirin::prelude::*;
use squin::Squin;

fn emit_text(text: &str) -> String {
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(text).unwrap();
    squin::emit::python::emit(&pipeline, "kernel", "main").unwrap()
}

#[test]
fn a_repeat_loop_becomes_a_body_function_and_a_call() {
    let text = emit_text(include_str!("../examples/rz_injection.kirin"));
    let expected = "import math

from bloqade import squin


@squin.kernel
def main():
    d0 = squin.qalloc(1)[0]
    squin.h(d0)
    def inject(d, t):
        anc = squin.qalloc(1)[0]
        squin.h(anc)
        squin.rz(t * math.tau, anc)
        squin.cx(d, anc)
        r = squin.measure(anc)
        done = squin.is_zero(r)
        t2 = t * 2.0
        return done, t2
    t1 = squin.repeat_until_success(inject, d0, 0.25)
    squin.s_adj(d0)
    squin.h(d0)
    r_1 = squin.measure(d0)
    return 0
";
    assert_eq!(text, expected);
}

#[test]
fn a_constant_angle_folds_into_radians() {
    let body = "%half = constant 0.5 -> Float;
                %a0 = alloc;
                %a1 = circuit %a0, %half digraph ^g(%q: Wire) capture(%t: Float) {
                  %q1 = rx(%t) %q;
                  yield %q1;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    let pipeline = common::kernel("", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    let expected = format!("squin.rx({:?}, a0)", std::f64::consts::PI);
    assert!(text.contains(&expected), "{text}");
    assert!(!text.contains("import math"), "{text}");
}

#[test]
fn a_conditional_assigns_its_classical_result_in_both_arms() {
    let body = "%one = constant 1 -> Int;
                %two = constant 2 -> Int;
                %a0 = alloc;
                %a1, %k = conditional %c (%a0) then block ^yes(%q: Wire) {
                  %q1 = circuit %q digraph ^flip(%w: Wire) {
                    %w1 = x %w;
                    yield %w1;
                  } -> Wire;
                  yield %q1, %one;
                } else block ^no(%e: Wire) {
                  yield %e, %two;
                } -> Wire, Int;
                free %a1;
                ret %k;";
    let pipeline = common::kernel("%c: Bool", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    let expected = "def main(c):
    a0 = squin.qalloc(1)[0]
    if c:
        squin.x(a0)
        k = 1
    else:
        k = 2
    return k
";
    assert!(text.ends_with(expected), "{text}");
}

#[test]
fn an_empty_else_arm_disappears() {
    let body = "%a0 = alloc;
                %a1 = conditional %c (%a0) then block ^yes(%q: Wire) {
                  %q1 = circuit %q digraph ^flip(%w: Wire) {
                    %w1 = x %w;
                    yield %w1;
                  } -> Wire;
                  yield %q1;
                } else block ^no(%e: Wire) {
                  yield %e;
                } -> Wire;
                free %a1;
                %n = constant 0 -> Int;
                ret %n;";
    let pipeline = common::kernel("%c: Bool", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    assert!(
        text.contains("    if c:\n        squin.x(a0)\n    return 0\n"),
        "{text}"
    );
    assert!(!text.contains("else"), "{text}");
}

#[test]
fn a_register_loop_indexes_the_list() {
    let text = emit_text(include_str!("../examples/address_loop.kirin"));
    assert!(
        text.contains("    for k in range(0, 3):\n        squin.h(r0[k])\n"),
        "{text}"
    );
    assert!(
        text.contains("    bits = squin.measure(r0)\n    return bits\n"),
        "{text}"
    );
}
