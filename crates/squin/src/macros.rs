//! Generate the trait impls that repeat for each statement.

/// Implement a trait with its default methods for each listed type.
///
/// `plain!(Structure for Alloc, Free);` writes `impl Structure for Alloc {}`
/// and the same line for `Free`.
macro_rules! plain {
    ($trait:path, for $($statement:ty),+ $(,)?) => {
        $(impl $trait for $statement {})+
    };
}

/// Implement the statement traits for an enum that wraps one statement in each variant.
///
/// Each method forwards to the statement of the variant. For example,
/// `delegate!(State { Alloc, Free });` makes `State::Alloc(inner).threads()`
/// return `inner.threads()`.
macro_rules! delegate {
    ($wrapper:ty { $($variant:ident),+ $(,)? }) => {
        impl $crate::threads::Threads for $wrapper {
            fn threads(&self) -> $crate::threads::Pairs {
                match self {
                    $(Self::$variant(inner) => inner.threads(),)+
                }
            }
        }

        impl $crate::verify::Typed for $wrapper {
            fn check(&self, typing: &mut $crate::verify::Typing<'_, '_>) {
                match self {
                    $(Self::$variant(inner) => inner.check(typing),)+
                }
            }
        }

        impl $crate::verify::Structure for $wrapper {
            fn nesting(&self) -> $crate::verify::Nesting<'_> {
                match self {
                    $(Self::$variant(inner) => inner.nesting(),)+
                }
            }

            fn lending(&self) -> Option<$crate::verify::Lending> {
                match self {
                    $(Self::$variant(inner) => inner.lending(),)+
                }
            }

            fn offset(&self) -> Option<$crate::verify::Offset> {
                match self {
                    $(Self::$variant(inner) => inner.offset(),)+
                }
            }
        }

        impl $crate::run::Execute for $wrapper {
            fn execute<B: $crate::run::Backend>(
                &self,
                machine: &mut $crate::run::Machine<'_, B>,
            ) -> Result<(), $crate::run::Failure> {
                match self {
                    $(Self::$variant(inner) => inner.execute(machine),)+
                }
            }
        }
    };
}

pub(crate) use {delegate, plain};
