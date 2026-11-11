use squin::Kernel;
use squin::runtime::stim::{Record, Stim};
use squin::runtime::{Backend, Value};

fn kernel(parameters: &str, result: &str, body: &str) -> Kernel {
    let types: Vec<_> = parameters
        .split(',')
        .filter_map(|parameter| parameter.split_once(':').map(|(_, ty)| ty.trim()))
        .collect();
    let signature = format!("fn @main({}) -> {result}", types.join(", "));
    Kernel::parse(&format!(
        "stage @kernel {signature};
         specialize @kernel {signature} cfg {{ ^entry({parameters}) {{ {body} }} }}"
    ))
    .unwrap()
}

#[test]
fn entry_arguments_must_have_the_declared_types() {
    let kernel = kernel("%n: Int", "Int", "ret %n;");
    assert!(
        kernel
            .run("main", vec![Value::from(0.5)], &mut Stim::default())
            .is_err()
    );
    assert_eq!(
        kernel
            .run("main", vec![Value::from(2_i64)], &mut Stim::default())
            .unwrap(),
        [Value::from(2_i64)]
    );
}

#[test]
fn any_arguments_accept_classical_values_and_preserve_ownership() {
    let kernel = kernel("%n: Any", "Any", "ret %n;");
    assert_eq!(
        kernel
            .run("main", vec![Value::Bool(true)], &mut Stim::default())
            .unwrap(),
        [Value::Bool(true)]
    );
    let mut backend = Stim::default();
    let qubit = backend.alloc().unwrap();
    assert!(
        kernel
            .run("main", vec![Value::Wire(qubit)], &mut backend)
            .is_err()
    );
    assert_eq!(backend.finish(), "");
}

#[test]
fn two_wire_arguments_must_own_distinct_qubits() {
    let kernel = kernel(
        "%a: Wire, %b: Wire",
        "Int",
        "%a1, %b1 = cx %a, %b;
         free %a1; free %b1; %n = constant 0 -> Int; ret %n;",
    );
    let mut backend = Stim::default();
    let qubit = backend.alloc().unwrap();
    assert!(
        kernel
            .run(
                "main",
                vec![Value::Wire(qubit), Value::Wire(qubit)],
                &mut backend
            )
            .is_err()
    );
    assert_eq!(backend.finish(), "");
    let mut backend = Stim::default();
    let a = backend.alloc().unwrap();
    let b = backend.alloc().unwrap();
    assert!(
        kernel
            .run("main", vec![Value::Wire(a), Value::Wire(b)], &mut backend)
            .is_ok()
    );
    assert_eq!(backend.finish(), "CX 0 1\n");
}

#[test]
fn register_arguments_must_match_their_length_and_lent_count() {
    let kernel = kernel("%r: Register[2]", "Register[2]", "ret %r;");
    let mut backend = Stim::default();
    let a = backend.alloc().unwrap();
    let b = backend.alloc().unwrap();
    for qubits in [vec![Some(a)], vec![Some(a), None], vec![Some(a), Some(a)]] {
        assert!(
            kernel
                .run("main", vec![Value::Register(qubits)], &mut backend)
                .is_err()
        );
    }
    let qubits = vec![Some(a), Some(b)];
    assert_eq!(
        kernel
            .run("main", vec![Value::Register(qubits.clone())], &mut backend)
            .unwrap(),
        [Value::Register(qubits)]
    );
}

#[test]
fn a_wire_argument_cannot_alias_a_register_element() {
    let kernel = kernel(
        "%a: Wire, %r: Register[1]",
        "Int",
        "free %a; free_register %r; %n = constant 0 -> Int; ret %n;",
    );
    let mut backend = Stim::default();
    let qubit = backend.alloc().unwrap();
    assert!(
        kernel
            .run(
                "main",
                vec![Value::Wire(qubit), Value::Register(vec![Some(qubit)])],
                &mut backend
            )
            .is_err()
    );
    assert_eq!(backend.finish(), "");
}

#[test]
fn measurement_arrays_must_match_the_declared_length() {
    let kernel = kernel("%bits: Bits[2]", "Bits[2]", "ret %bits;");
    assert!(
        kernel
            .run(
                "main",
                vec![Value::Bits(vec![Record(0)])],
                &mut Stim::default()
            )
            .is_err()
    );
    assert!(
        kernel
            .run(
                "main",
                vec![Value::Bits(vec![Record(0), Record(1)])],
                &mut Stim::default()
            )
            .is_ok()
    );
}

#[test]
fn execution_selects_the_most_specific_matching_specialization() {
    let text = "stage @kernel fn @main(Any) -> Any;
        specialize @kernel fn @main(Any) -> Any cfg {
          ^generic(%n: Any) { ret %n; }
        }
        specialize @kernel fn @main(Int) -> Int cfg {
          ^integer(%n: Int) { %one = constant 1 -> Int; %v = add %n, %one -> Int; ret %v; }
        }
        specialize @kernel fn @main(Float) -> Float cfg {
          ^float(%n: Float) { %one = constant 1.0 -> Float; %v = add %n, %one -> Float; ret %v; }
        }";
    let kernel = Kernel::parse(text).unwrap();
    for (argument, expected) in [
        (Value::from(0.5), Value::from(1.5)),
        (Value::from(2_i64), Value::from(3_i64)),
        (Value::Bool(true), Value::Bool(true)),
    ] {
        assert_eq!(
            kernel
                .run("main", vec![argument], &mut Stim::default())
                .unwrap(),
            [expected]
        );
    }
}

#[test]
fn ambiguous_specializations_require_an_error() {
    let text = "stage @kernel fn @main(Any, Any) -> Int;
        specialize @kernel fn @main(Int, Any) -> Int cfg {
          ^left(%a: Int, %b: Any) { ret %a; }
        }
        specialize @kernel fn @main(Any, Int) -> Int cfg {
          ^right(%a: Any, %b: Int) { ret %b; }
        }";
    let kernel = Kernel::parse(text).unwrap();
    assert!(
        kernel
            .run(
                "main",
                vec![Value::from(1_i64), Value::from(2_i64)],
                &mut Stim::default()
            )
            .is_err()
    );
}

#[test]
fn unmatched_specializations_require_an_error() {
    let text = "stage @kernel fn @main(Any) -> Any;
        specialize @kernel fn @main(Int) -> Int cfg { ^integer(%n: Int) { ret %n; } }
        specialize @kernel fn @main(Float) -> Float cfg { ^float(%n: Float) { ret %n; } }";
    let kernel = Kernel::parse(text).unwrap();
    assert!(
        kernel
            .run("main", vec![Value::Bool(true)], &mut Stim::default())
            .is_err()
    );
}
