//! Write the struct and the `Threads` impl of each gate of a family.
//!
//! The gates of one family have the same fields. Each macro takes a list of
//! `Name = "format";` entries and expands each entry where the gate module
//! calls it, so the struct uses that module's imports.

/// Define each gate that takes one qubit and no angle.
macro_rules! single_qubit_gates {
    ($($(#[$doc:meta])* $name:ident = $format:tt;)+) => {$(
        $(#[$doc])*
        #[derive(Debug, Clone, PartialEq, Eq, Hash, Dialect, HasParser, PrettyPrint)]
        #[kirin(pure, builders, type = SquinType)]
        #[chumsky(format = $format)]
        pub struct $name {
            pub wire: SSAValue,
            #[kirin(type = SquinType::Wire)]
            pub wire_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

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
            #[kirin(type = SquinType::Wire)]
            pub wire_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.wire, self.wire_out)]
            }
        }

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
            #[kirin(type = SquinType::Wire)]
            pub control_out: ResultValue,
            #[kirin(type = SquinType::Wire)]
            pub target_out: ResultValue,
        }

        impl Threads for $name {
            fn threads(&self) -> Pairs {
                smallvec![(self.control, self.control_out), (self.target, self.target_out)]
            }
        }

    )+};
}

pub(super) use {controlled_gates, rotation_gates, single_qubit_gates};
