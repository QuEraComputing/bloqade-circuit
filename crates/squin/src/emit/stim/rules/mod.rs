//! Give each statement in squin its `EmitStim` rule.
//!
//! Each file holds the rules of one group of dialects. A Stim circuit holds
//! quantum instructions only, so the rules of classical statements write
//! nothing.

mod classical;
mod control;
mod gate;
mod qubit;

/// Write an `EmitStim` rule that writes nothing for each listed statement.
macro_rules! nothing {
    ($($statement:ty),+ $(,)?) => {$(
        impl<'a> kirin_interpreter::dialect::Interpretable<
            crate::emit::stim::StimEmitter<'a>,
            crate::emit::stim::EmitStim,
        > for $statement {
            fn interpret(
                &self,
                _emitter: &mut crate::emit::stim::StimEmitter<'a>,
            ) -> Result<(), crate::emit::stim::StimError> {
                Ok(())
            }
        }
    )+};
}

use nothing;
