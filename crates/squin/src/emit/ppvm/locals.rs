//! Give each classical value of a function a local slot of the ppvm CPU.
//!
//! The CPU keeps locals on its operand stack, at the frame base plus the slot
//! number. The writer reserves every slot when the function starts, so the
//! operands of later instructions sit above the locals.

use std::collections::HashMap;
use std::fmt;

use kirin::prelude::SSAValue;
use kirin_arith::ArithType;

use crate::ir::types::{Length, SquinType};

/// Name the ppvm type of one local.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Kind {
    I64,
    F64,
    Bool,
    /// A measurement outcome: 0 for zero, 1 for one, and 2 for a lost atom.
    U32,
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
        };
        write!(f, "{name}")
    }
}

/// One local slot with its kind.
pub(super) type Slot = (u32, Kind);

/// Hold the slots of each classical value.
///
/// A `MeasurementResults[N]` value has `N` slots, one for each outcome.
#[derive(Default)]
pub(super) struct Locals {
    slots: HashMap<SSAValue, Vec<Slot>>,
    next: u32,
}

impl Locals {
    /// Return the number of slots that the function uses.
    pub(super) fn count(&self) -> u32 {
        self.next
    }

    /// Give `value` of type `ty` new slots, and return them.
    ///
    /// The result is empty for a quantum value, which has no slot.
    pub(super) fn define(&mut self, value: SSAValue, ty: SquinType) -> Vec<Slot> {
        let kinds = match ty {
            SquinType::MeasurementResults(Length::Known(len)) => vec![Kind::U32; len as usize],
            ty => Kind::of(ty).into_iter().collect(),
        };
        let slots: Vec<Slot> = kinds
            .into_iter()
            .map(|kind| {
                self.next += 1;
                (self.next - 1, kind)
            })
            .collect();
        if !slots.is_empty() {
            self.slots.insert(value, slots.clone());
        }
        slots
    }

    /// Return the slots of `value`, or `None` if the writer gave it none.
    pub(super) fn get(&self, value: SSAValue) -> Option<&[Slot]> {
        self.slots.get(&value).map(Vec::as_slice)
    }

    /// Let `value` share the slots of `target`, as a port shares its input.
    pub(super) fn alias(&mut self, value: SSAValue, target: SSAValue) {
        if let Some(slots) = self.slots.get(&target).cloned() {
            self.slots.insert(value, slots);
        }
    }

    /// Let `value` use the given slots.
    pub(super) fn set(&mut self, value: SSAValue, slots: Vec<Slot>) {
        self.slots.insert(value, slots);
    }
}
