//! Give each classical value of a function a local slot of the ppvm CPU.
//!
//! The CPU keeps locals on its operand stack, at the frame base plus the slot
//! number. The emitter reserves every slot when the function starts, so the
//! operands of later instructions sit above the locals.

use std::fmt;

use kirin_arith::ArithType;

use crate::ir::types::{Length, SquinType};

/// Name the ppvm type of one local.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    I64,
    F64,
    Bool,
    /// A measurement outcome: 0 for zero, 1 for one, and 2 for a lost atom.
    U32,
    /// A qubit index that the program reads from a register table at run time.
    U64,
    /// A reference to a vihaco heap array, such as a register table.
    HeapRef,
}

impl Kind {
    /// Return the kind of a value of type `ty`, or `None` for a quantum type.
    pub(super) fn of(ty: SquinType) -> Option<Kind> {
        match ty {
            SquinType::Number(ArithType::I64) => Some(Kind::I64),
            SquinType::Number(ArithType::F64) => Some(Kind::F64),
            SquinType::Bool => Some(Kind::Bool),
            SquinType::MeasurementResult => Some(Kind::U32),
            _ => None,
        }
    }
}

impl fmt::Display for Kind {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let name = match self {
            Kind::I64 => "i64",
            Kind::F64 => "f64",
            Kind::Bool => "bool",
            Kind::U32 => "u32",
            Kind::U64 => "u64",
            Kind::HeapRef => "heap_ref",
        };
        write!(f, "{name}")
    }
}

/// One local slot with its kind.
pub type Slot = (u32, Kind);

/// Return the kind of each slot of a value of type `ty`.
///
/// A `MeasurementResults[N]` value has `N` slots, one for each outcome. A
/// quantum value has no slot, so its list is empty.
pub(super) fn kinds(ty: SquinType) -> Vec<Kind> {
    match ty {
        SquinType::MeasurementResults(Length::Known(len)) => vec![Kind::U32; len as usize],
        ty => Kind::of(ty).into_iter().collect(),
    }
}
