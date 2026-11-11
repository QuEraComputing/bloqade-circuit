//! Check that the evaluator runs every kernel that the verifier accepts.
//!
//! The test builds many small kernels from a fixed sequence of random numbers.
//! Some kernels break a rule on purpose. For example, one releases a wire into
//! the slot of another qubit, and one borrows the same element twice.

use squin::run::{Backend, Failure, Operation, Qubit};
use squin::{Kernel, KernelError};

/// Give the same sequence of numbers for the same seed.
struct Random(u64);

impl Random {
    /// Return a number below `bound`.
    fn below(&mut self, bound: usize) -> usize {
        self.0 = self
            .0
            .wrapping_mul(6364136223846793005)
            .wrapping_add(1442695040888963407);
        ((self.0 >> 33) as usize) % bound
    }

    fn chance(&mut self, percent: usize) -> bool {
        self.below(100) < percent
    }
}

/// Accept every operation and report each measurement as false.
#[derive(Default)]
struct Null(u32);

impl Backend for Null {
    type Bit = bool;

    fn alloc(&mut self) -> Result<Qubit, Failure> {
        self.0 += 1;
        Ok(Qubit(self.0 - 1))
    }

    fn free(&mut self, _qubit: Qubit) -> Result<(), Failure> {
        Ok(())
    }

    fn gate(&mut self, _operation: Operation, _qubits: &[Qubit]) -> Result<(), Failure> {
        Ok(())
    }

    fn measure(&mut self, qubits: &[Qubit]) -> Result<Vec<bool>, Failure> {
        Ok(vec![false; qubits.len()])
    }

    fn reset(&mut self, _qubit: Qubit) -> Result<(), Failure> {
        Ok(())
    }
}

const SIZE: usize = 3;

/// Write a kernel on a register of `SIZE` qubits and track its wires and slots.
struct Builder {
    random: Random,
    lines: Vec<String>,
    /// The number of names that the builder has made.
    names: usize,
    register: String,
    /// The slots that no `release` has consumed, each with the wire that left it.
    open: Vec<(String, String)>,
    /// The wires that no statement has consumed.
    wires: Vec<String>,
    /// A wire that a statement has consumed, for a second use on purpose.
    spent: Option<String>,
}

impl Builder {
    fn new(seed: u64) -> Self {
        let mut lines = vec![format!("%n = constant {SIZE} -> Int;")];
        lines.extend((0..SIZE).map(|index| format!("%i{index} = constant {index} -> Int;")));
        lines.push(format!("%r = alloc_register %n -> {};", register_type(0)));
        Self {
            random: Random(seed),
            lines,
            names: 0,
            register: "%r".to_string(),
            open: Vec::new(),
            wires: Vec::new(),
            spent: None,
        }
    }

    fn name(&mut self, prefix: &str) -> String {
        self.names += 1;
        format!("%{prefix}{}", self.names)
    }

    /// Remove a random live wire. A small share of the calls return a spent wire.
    fn take_wire(&mut self) -> Option<String> {
        if self.random.chance(5) && self.spent.is_some() {
            return self.spent.clone();
        }
        if self.wires.is_empty() {
            return None;
        }
        let wire = self.wires.remove(self.random.below(self.wires.len()));
        self.spent = Some(wire.clone());
        Some(wire)
    }

    /// Give the wire `old` the new name `new` in the list of open slots.
    fn rename(&mut self, old: &str, new: &str) {
        for (_, wire) in &mut self.open {
            if wire == old {
                *wire = new.to_string();
            }
        }
    }

    fn borrow(&mut self) {
        let index = self.random.below(SIZE);
        let (register, slot, wire) = (self.name("r"), self.name("s"), self.name("w"));
        let lent = self.open.len() + 1;
        self.lines.push(format!(
            "{register}, {slot}, {wire} = borrow {}, %i{index} -> {}, Slot, Wire;",
            self.register,
            register_type(lent)
        ));
        self.register = register;
        self.open.push((slot, wire.clone()));
        self.wires.push(wire);
    }

    fn gate(&mut self) {
        let Some(wire) = self.take_wire() else { return };
        let next = self.name("w");
        self.lines.push(format!("{next} = h {wire} -> Wire;"));
        self.rename(&wire, &next);
        self.wires.push(next);
    }

    /// Release a random open slot. `exact` selects the wire that left the slot.
    fn release(&mut self, exact: bool) {
        if self.open.is_empty() {
            return;
        }
        let (slot, own) = self.open.remove(self.random.below(self.open.len()));
        let wire = if exact {
            self.wires.retain(|wire| *wire != own);
            Some(own)
        } else {
            self.take_wire()
        };
        let Some(wire) = wire else { return };
        let register = self.name("r");
        self.lines.push(format!(
            "{register} = release {}, {slot}, {wire} -> {};",
            self.register,
            register_type(self.open.len())
        ));
        self.register = register;
    }

    /// Finish the kernel. `tidy` releases every slot with its own wire first.
    fn finish(mut self, tidy: bool) -> String {
        while tidy && !self.open.is_empty() {
            self.release(true);
        }
        for wire in std::mem::take(&mut self.wires) {
            self.lines.push(format!("free {wire};"));
        }
        self.lines.push(format!("free_register {};", self.register));
        self.lines.push("ret %n;".to_string());
        format!(
            "stage @kernel fn @main() -> Int;\n\
             specialize @kernel fn @main() -> Int cfg {{\n  ^entry() {{\n{}\n  }}\n}}\n",
            self.lines.join("\n")
        )
    }
}

fn register_type(lent: usize) -> String {
    match lent {
        0 => format!("Register[{SIZE}]"),
        lent => format!("Register[{SIZE}; lent={lent}]"),
    }
}

/// Return the text of the kernel that the seed selects.
fn kernel(seed: u64) -> String {
    let mut builder = Builder::new(seed);
    for _ in 0..builder.random.below(12) {
        match builder.random.below(4) {
            0 => builder.borrow(),
            1 | 2 => builder.gate(),
            _ => {
                let exact = builder.random.chance(70);
                builder.release(exact);
            }
        }
    }
    let tidy = builder.random.chance(80);
    builder.finish(tidy)
}

#[test]
fn the_evaluator_runs_every_kernel_that_the_verifier_accepts() {
    let (mut accepted, mut rejected) = (0, 0);
    for seed in 0..2000 {
        let text = kernel(seed);
        match Kernel::parse(&text) {
            Ok(kernel) => {
                let result = kernel.run("main", Vec::new(), &mut Null::default());
                assert!(result.is_ok(), "seed {seed}: {result:?}\n{text}");
                accepted += 1;
            }
            Err(KernelError::Invalid(_)) => rejected += 1,
            Err(error) => panic!("seed {seed}: the builder wrote bad text: {error}\n{text}"),
        }
    }
    assert!(accepted > 200, "the verifier accepted {accepted} kernels");
    assert!(rejected > 200, "the verifier rejected {rejected} kernels");
}
