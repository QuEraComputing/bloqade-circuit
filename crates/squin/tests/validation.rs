mod common;

use kirin::prelude::*;
use squin::Rule;

fn program(body: &str) -> String {
    format!(
        "stage @kernel fn @main() -> Int;
         specialize @kernel fn @main() -> Int cfg {{ ^entry() {{ {body} }} }}"
    )
}

fn rejects(body: &str) {
    assert!(matches!(
        common::check(&program(body)),
        Err(common::Rejected::Invalid(_))
    ));
}

#[test]
fn a_value_cannot_cross_between_conditional_arms() {
    rejects(
        "%c = constant false -> Bool;
         %v = if %c then block ^then() {
           %x = constant 7 -> Int;
           yield %x;
         } else block ^else() { yield %x; } -> Int;
         ret %v;",
    );
}

#[test]
fn a_value_cannot_escape_a_loop_body() {
    rejects(
        "%z = constant 0 -> Int;
         %o = constant 1 -> Int;
         for %z in %z..%z step %o iter_args() do block ^body(%k: Int) {
           %x = constant 7 -> Int;
           yield;
         };
         ret %x;",
    );
}

#[test]
fn a_loop_body_requires_an_integer_index() {
    for arguments in ["", "%k: Float", "%k: Bool"] {
        rejects(&format!(
            "%z = constant 0 -> Int;
             %o = constant 1 -> Int;
             for %z in %z..%o step %o iter_args() do block ^body({arguments}) {{ yield; }};
             ret %z;"
        ));
    }
}

#[test]
fn a_loop_cannot_consume_a_wire_as_its_index_operand() {
    rejects(
        "%z = constant 0 -> Int;
         %o = constant 1 -> Int;
         %a = alloc;
         for %a in %z..%o step %o iter_args() do block ^body(%k: Int) { yield; };
         ret %z;",
    );
}

#[test]
fn conditional_arms_require_no_arguments() {
    rejects(
        "%c = constant true -> Bool;
         %n = constant 0 -> Int;
         %x = if %c then block ^then(%p: Int) { yield %p; }
         else block ^else() { yield %n; } -> Int;
         ret %x;",
    );
}

#[test]
fn nested_blocks_require_yield_terminators() {
    rejects(
        "%c = constant true -> Bool;
         %n = constant 0 -> Int;
         %x = if %c then block ^then() { ret %n; }
         else block ^else() { yield %n; } -> Int;
         ret %x;",
    );
}

#[test]
fn function_blocks_require_return_terminators() {
    rejects("%n = constant 0 -> Int; yield %n;");
}

#[test]
fn outer_values_remain_visible_in_nested_blocks() {
    let text = program(
        "%n = constant 0 -> Int;
         %o = constant 1 -> Int;
         %c = constant true -> Bool;
         %answer = for %n in %n..%o step %o iter_args(%n) do block ^body(%k: Int, %sum: Int) {
           %next = if %c then block ^then() {
             %v = add %sum, %o -> Int;
             yield %v;
           } else block ^else() { yield %k; } -> Int;
           yield %next;
         } -> Int;
         ret %answer;",
    );
    assert!(common::check(&text).is_ok(), "{text}");
}

#[test]
fn a_borrow_count_cannot_overflow() {
    let text = "stage @kernel fn @main(Register[?; lent=4294967295]) -> Register[?];
                specialize @kernel fn @main(Register[?; lent=4294967295]) -> Register[?] cfg {
                  ^entry(%r: Register[?; lent=4294967295]) {
                    %i = constant 0 -> Int;
                    %r1, %s, %a = borrow %r, %i -> Register[?];
                    free %a;
                    ret %r1;
                  }
                }";
    let Err(common::Rejected::Invalid(errors)) = common::check(text) else {
        panic!("The verifier must reject the borrow count.");
    };
    assert!(errors.iter().any(|error| error.rule() == Rule::Type));
}

#[test]
fn a_register_cannot_have_more_open_borrows_than_elements() {
    let text = "stage @kernel fn @main(Register[2; lent=3]) -> Register[2; lent=3];
                specialize @kernel fn @main(Register[2; lent=3]) -> Register[2; lent=3] cfg {
                  ^entry(%r: Register[2; lent=3]) { ret %r; }
                }";
    assert!(matches!(
        common::check(text),
        Err(common::Rejected::Invalid(_))
    ));
}

#[test]
fn float_literals_must_stay_finite() {
    for value in ["1.0e309", "-1.0e309"] {
        let text = program(&format!(
            "%x = constant {value} -> Float; %n = constant 0 -> Int; ret %n;"
        ));
        assert!(matches!(
            common::check(&text),
            Err(common::Rejected::Parse(_))
        ));
    }
    let kernel = common::check(&program(
        "%x = constant 1.0e308 -> Float; %n = constant 0 -> Int; ret %n;",
    ))
    .unwrap();
    assert!(common::check(&kernel.sprint()).is_ok());
}

#[test]
fn shared_index_expressions_have_bounded_analysis_work() {
    let mut body =
        String::from("%n = constant 2 -> Int; %o = constant 1 -> Int; %v0 = constant 0 -> Int;");
    for index in 1..=64 {
        let previous = index - 1;
        body.push_str(&format!(
            "%v{index} = add %v{previous}, %v{previous} -> Int;"
        ));
    }
    body.push_str(
        "%r = alloc_register %n -> Register[2];
         %r1, %s, %a = borrow %r, %o -> Register[2; lent=1];
         %r2, %t, %b = borrow %r1, %v64 -> Register[2; lent=2];
         %r3 = release %r2, %t, %b -> Register[2; lent=1];
         %r4 = release %r3, %s, %a -> Register[2];
         free_register %r4;
         ret %n;",
    );
    assert!(common::check(&program(&body)).is_ok());
}
