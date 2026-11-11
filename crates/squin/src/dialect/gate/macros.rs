//! Generate the repeated fields and rules of each gate family.

/// Define each gate that takes one qubit and no angle.
macro_rules! single_qubit_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub wire: SSAValue,
            pub wire_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

        impl Typed for $name {
            fn check<C: TypeCheck>(&self, typing: &mut C) {
                check(typing, &self.threads(), &[]);
            }
        }

        impl Execute for $name {
            fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
                apply(machine, Operation::$name, &self.threads())
            }
        }

        plain!(Structure, for $name);
    )+};
}

/// Define each rotation of one qubit by one angle.
macro_rules! rotation_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub angle: SSAValue,
            pub wire: SSAValue,
            pub wire_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

        impl Typed for $name {
            fn check<C: TypeCheck>(&self, typing: &mut C) {
                check(typing, &self.threads(), &[self.angle]);
            }
        }

        impl Execute for $name {
            fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
                let angle = machine.float(self.angle)?;
                apply(machine, Operation::$name(angle), &self.threads())
            }
        }

        plain!(Structure, for $name);
    )+};
}

/// Define each gate that applies a Pauli to `target` if `control` is in the one state.
macro_rules! controlled_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub control: SSAValue,
            pub target: SSAValue,
            pub control_out: ResultValue,
            pub target_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.control, self.control_out), (self.target, self.target_out)]
            }
        }

        impl Typed for $name {
            fn check<C: TypeCheck>(&self, typing: &mut C) {
                check(typing, &self.threads(), &[]);
            }
        }

        impl Execute for $name {
            fn execute<E: Evaluator>(&self, machine: &mut E) -> Result<(), Failure> {
                apply(machine, Operation::$name, &self.threads())
            }
        }

        plain!(Structure, for $name);
    )+};
}

pub(super) use {controlled_gates, rotation_gates, single_qubit_gates};
