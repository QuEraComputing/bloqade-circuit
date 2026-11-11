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
        impl $crate::dialect::traits::Threads for $wrapper {
            fn threads(&self) -> $crate::dialect::traits::Pairs {
                match self {
                    $(Self::$variant(inner) => inner.threads(),)+
                }
            }
        }

        impl $crate::dialect::traits::Typed for $wrapper {
            fn check<C: $crate::dialect::traits::TypeCheck>(&self, typing: &mut C) {
                match self {
                    $(Self::$variant(inner) => inner.check(typing),)+
                }
            }
        }

        impl $crate::dialect::traits::Structure for $wrapper {
            fn nesting(&self) -> $crate::dialect::traits::Nesting<'_> {
                match self {
                    $(Self::$variant(inner) => inner.nesting(),)+
                }
            }

            fn lending(&self) -> Option<$crate::dialect::traits::Lending> {
                match self {
                    $(Self::$variant(inner) => inner.lending(),)+
                }
            }

            fn offset(&self) -> Option<$crate::dialect::traits::Offset> {
                match self {
                    $(Self::$variant(inner) => inner.offset(),)+
                }
            }
        }

        impl $crate::dialect::traits::Execute for $wrapper {
            fn execute<E: $crate::dialect::traits::Evaluator>(
                &self,
                machine: &mut E,
            ) -> Result<(), $crate::dialect::semantics::Failure> {
                match self {
                    $(Self::$variant(inner) => inner.execute(machine),)+
                }
            }
        }
    };
}

pub(crate) use {delegate, plain};
