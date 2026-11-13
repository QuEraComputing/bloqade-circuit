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

#[test]
fn a_replace_writes_the_new_wire_into_the_list() {
    let text = emit_text(include_str!("../examples/address.kirin"));
    let expected = "    old = r0[1]\n    r0[1] = fresh\n    bits = squin.measure(r0)\n";
    assert!(text.contains(expected), "{text}");
}

#[test]
fn split_join_and_pack_become_list_operations() {
    let body = "%one = constant 1 -> Int;
                %two = constant 2 -> Int;
                %a0 = alloc;
                %b0 = alloc;
                %r0 = pack %a0, %b0 -> Register[2];
                %head, %tail = split %r0, %one -> Register[1], Register[1];
                %r1 = join %tail, %head -> Register[2];
                free_register %r1;
                ret %two;";
    let pipeline = common::kernel("", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    for expected in [
        "    r0 = [a0, b0]\n",
        "    head = r0[:1]\n    tail = r0[1:]\n",
        "    r1 = tail + head\n",
    ] {
        assert!(text.contains(expected), "{expected}\n{text}");
    }
}

#[test]
fn a_branch_that_swaps_its_wires_assigns_them_in_both_arms() {
    let body = "%a0 = alloc;
                %b0 = alloc;
                %x, %y = conditional %c (%a0, %b0) then block ^swap(%p: Wire, %q: Wire) {
                  yield %q, %p;
                } else block ^keep(%s: Wire, %t: Wire) {
                  yield %s, %t;
                } -> Wire, Wire;
                %x1 = circuit %x digraph ^g(%w: Wire) {
                  %w1 = h %w;
                  yield %w1;
                } -> Wire;
                free %x1;
                free %y;
                %n = constant 0 -> Int;
                ret %n;";
    let pipeline = common::kernel("%c: Bool", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    let expected = "    if c:
        x = b0
        y = a0
    else:
        x = a0
        y = b0
    squin.h(x)
";
    assert!(text.contains(expected), "{text}");
}

#[test]
fn integer_division_rounds_toward_zero() {
    let body = "%a = constant -7 -> Int;
                %b = constant 2 -> Int;
                %q = div %a, %b -> Int;
                %r = rem %a, %b -> Int;
                %x = constant 7.5 -> Float;
                %y = constant 2.0 -> Float;
                %f = rem %x, %y -> Float;
                %s = add %q, %r -> Int;
                ret %s;";
    let pipeline = common::kernel("", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    assert!(text.starts_with("import math\n"), "{text}");
    assert!(text.contains("def trunc_div(a, b):"), "{text}");
    assert!(
        text.contains("    q = trunc_div(-7, 2)\n    r = trunc_rem(-7, 2)\n"),
        "{text}"
    );
    assert!(text.contains("    f = math.fmod(7.5, 2.0)\n"), "{text}");
}

#[test]
fn a_python_keyword_gets_a_suffix() {
    let body = "%class = constant 1 -> Int;
                %from = add %class, %class -> Int;
                ret %from;";
    let pipeline = common::kernel("", body);
    let text = squin::emit::python::emit(&pipeline, "kernel", "main").unwrap();
    assert!(
        text.contains("    from_ = 1 + 1\n    return from_\n"),
        "{text}"
    );
}
