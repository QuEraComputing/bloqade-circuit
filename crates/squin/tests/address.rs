//! Check the qubit that the address analysis finds for each wire.

use kirin::prelude::*;
use squin::Squin;
use squin::analysis::address::{self, Address, Addresses, QubitId};

/// Parse a kernel `@main` with `parameters` and `body`, which must return `%n`.
fn program(parameters: &str, body: &str) -> Pipeline<StageInfo<Squin>> {
    let types: Vec<&str> = parameters
        .split(',')
        .filter_map(|parameter| parameter.split(':').nth(1))
        .map(str::trim)
        .collect();
    let signature = format!("fn @main({}) -> Int", types.join(", "));
    let text = format!(
        "stage @kernel {signature};
         specialize @kernel {signature} cfg {{
           ^entry({parameters}) {{
             {body}
             ret %n;
           }}
         }}"
    );
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(&text).expect("the kernel parses");
    let stage = pipeline.stage_by_name("kernel").unwrap();
    assert!(
        squin::verify(pipeline.stage(stage).unwrap()).is_ok(),
        "{text}"
    );
    pipeline
}

/// Return the SSA value that the program text names `name`, such as `%a1`.
fn value(pipeline: &Pipeline<StageInfo<Squin>>, name: &str) -> SSAValue {
    let stage = pipeline
        .stage(pipeline.stage_by_name("kernel").unwrap())
        .unwrap();
    let wanted = name.trim_start_matches('%');
    let mut values = stage.ssa_arena().iter().filter_map(|item| item.as_ref());
    let found = values.find(|info| {
        let name = info
            .name()
            .and_then(|symbol| stage.symbol_table().resolve(symbol));
        name.map(String::as_str) == Some(wanted)
    });
    found
        .unwrap_or_else(|| panic!("the program names {name}"))
        .id()
}

/// Return the facts of `names`, in order.
fn facts(
    pipeline: &Pipeline<StageInfo<Squin>>,
    addresses: &Addresses<'_>,
    names: &[&str],
) -> Vec<Address> {
    names
        .iter()
        .map(|name| addresses.of(value(pipeline, name)))
        .collect()
}

fn qubit(fact: &Address) -> QubitId {
    fact.qubit()
        .unwrap_or_else(|| panic!("{fact:?} names no qubit"))
}

#[test]
fn a_gate_keeps_the_qubit_of_each_wire() {
    let pipeline = program(
        "",
        "%a0 = alloc;
         %b0 = alloc;
         %a2, %b1 = circuit %a0, %b0 digraph ^g0(%a0: Wire, %b0: Wire) {
           %a1 = h %a0;
           %a2, %b1 = cx %a1, %b0;
           yield %a2, %b1;
         } -> Wire, Wire;
         free %a2;
         free %b1;
         %n = constant 0 -> Int;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let [a0, b0, a1, a2, b1] = facts(&pipeline, &addresses, &["%a0", "%b0", "%a1", "%a2", "%b1"])
        .try_into()
        .unwrap();
    assert_eq!(qubit(&a0), qubit(&a1));
    assert_eq!(qubit(&a0), qubit(&a2));
    assert_eq!(qubit(&b0), qubit(&b1));
    assert_ne!(qubit(&a0), qubit(&b0));
}

#[test]
fn a_borrow_at_a_computed_index_takes_that_element() {
    let pipeline = program(
        "",
        "%n = constant 3 -> Int;
         %one = constant 1 -> Int;
         %last = sub %n, %one -> Int;
         %r0 = alloc_register %n -> Register[3];
         %r1, %s, %a0 = borrow %r0, %last -> Register[3; lent=1];
         %a1 = circuit %a0 digraph ^g1(%a0: Wire) {
           %a1 = x %a0;
           yield %a1;
         } -> Wire;
         %r2 = release %r1, %s, %a1 -> Register[3];
         free_register %r2;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let [r0, a1, r2] = facts(&pipeline, &addresses, &["%r0", "%a1", "%r2"])
        .try_into()
        .unwrap();
    let elements = r0.qubits().expect("the register has known qubits").to_vec();
    assert_eq!(elements.len(), 3);
    assert_eq!(qubit(&a1), elements[2]);
    assert_eq!(r2, r0);
}

#[test]
fn a_replace_moves_a_fresh_qubit_into_the_register() {
    let pipeline = program(
        "",
        "%n = constant 2 -> Int;
         %one = constant 1 -> Int;
         %r0 = alloc_register %n -> Register[2];
         %fresh = alloc;
         %r1, %old = replace %r0, %one, %fresh -> Register[2];
         free %old;
         free_register %r1;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let [r0, fresh, r1, old] = facts(&pipeline, &addresses, &["%r0", "%fresh", "%r1", "%old"])
        .try_into()
        .unwrap();
    let before = r0.qubits().unwrap();
    let after = r1.qubits().unwrap();
    assert_eq!(qubit(&old), before[1]);
    assert_eq!(after, [before[0], qubit(&fresh)]);
}

#[test]
fn an_if_with_an_unknown_condition_keeps_a_qubit_that_both_arms_yield() {
    let pipeline = program(
        "%c: Bool",
        "%a0 = alloc;
         %a1 = conditional %c (%a0) then block ^then(%t: Wire) {
           %flipped = circuit %t digraph ^g2(%t: Wire) {
             %flipped = x %t;
             yield %flipped;
           } -> Wire;
           yield %flipped;
         } else block ^else(%e: Wire) {
           yield %e;
         } -> Wire;
         free %a1;
         %n = constant 0 -> Int;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let [a0, a1] = facts(&pipeline, &addresses, &["%a0", "%a1"])
        .try_into()
        .unwrap();
    assert_eq!(qubit(&a0), qubit(&a1));
}

#[test]
fn a_borrow_at_a_loop_index_has_no_fixed_qubit() {
    let pipeline = program(
        "",
        "%n = constant 3 -> Int;
         %zero = constant 0 -> Int;
         %one = constant 1 -> Int;
         %r0 = alloc_register %n -> Register[3];
         %r3 = for %zero in %zero..%n step %one iter_args(%r0) do block ^body(%k: Int, %r: Register[3]) {
           %r1, %s, %a0 = borrow %r, %k -> Register[3; lent=1];
           %a1 = circuit %a0 digraph ^g3(%a0: Wire) {
             %a1 = h %a0;
             yield %a1;
           } -> Wire;
           %r2 = release %r1, %s, %a1 -> Register[3];
           yield %r2;
         } -> Register[3];
         free_register %r3;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let [r0, a1, r3] = facts(&pipeline, &addresses, &["%r0", "%a1", "%r3"])
        .try_into()
        .unwrap();
    assert_eq!(a1, Address::Top);
    assert_eq!(
        r3, r0,
        "a borrow and its release leave the register unchanged"
    );
}

#[test]
fn pack_split_and_join_keep_the_order_of_the_qubits() {
    let pipeline = program(
        "",
        "%a = alloc;
         %b = alloc;
         %c = alloc;
         %r0 = pack %a, %b, %c -> Register[3];
         %one = constant 1 -> Int;
         %front, %back = split %r0, %one -> Register[?], Register[?];
         %r1 = join %back, %front -> Register[?];
         %r2, %n = length %r1 -> Register[?];
         free_register %r2;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let [a, b, c, r1, n] = facts(&pipeline, &addresses, &["%a", "%b", "%c", "%r1", "%n"])
        .try_into()
        .unwrap();
    assert_eq!(r1.qubits().unwrap(), [qubit(&b), qubit(&c), qubit(&a)]);
    assert_eq!(n, Address::Int(3));
}

#[test]
fn a_register_with_a_size_argument_has_no_known_qubits() {
    let pipeline = program(
        "%size: Int",
        "%r0 = alloc_register %size -> Register[?];
         %r1, %n = length %r0 -> Register[?];
         free_register %r1;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    assert_eq!(addresses.of(value(&pipeline, "%r0")), Address::Top);
}

#[test]
fn a_function_with_two_specializations_is_an_error() {
    let text = "stage @kernel fn @main(Any) -> Int;
        specialize @kernel fn @main(Int) -> Int cfg {
          ^entry(%x: Int) { ret %x; }
        }
        specialize @kernel fn @main(Any) -> Int cfg {
          ^entry(%x: Any) { %n = constant 0 -> Int; ret %n; }
        }";
    let mut pipeline: Pipeline<StageInfo<Squin>> = Pipeline::new();
    pipeline.parse(text).expect("the program parses");
    let error = address::analyze(&pipeline, "kernel", "main")
        .err()
        .expect("two bodies");
    assert!(
        matches!(
            error,
            address::AddressError::Specializations { count: 2, .. }
        ),
        "{error}"
    );
}

#[test]
fn known_truth_values_stay_known_through_bitwise_statements() {
    let pipeline = program(
        "",
        "%t = constant true -> Bool;
         %f = constant false -> Bool;
         %x = xor %t, %f -> Bool;
         %y = and %x, %f -> Bool;
         %z = not %y -> Bool;
         %n = constant 6 -> Int;
         %two = constant 2 -> Int;
         %m = shr %n, %two -> Int;",
    );
    let addresses = address::analyze(&pipeline, "kernel", "main").unwrap();
    let found = facts(&pipeline, &addresses, &["%x", "%y", "%z", "%m"]);
    assert_eq!(
        found,
        [
            Address::Bool(true),
            Address::Bool(false),
            Address::Bool(true),
            Address::Int(1)
        ]
    );
}
