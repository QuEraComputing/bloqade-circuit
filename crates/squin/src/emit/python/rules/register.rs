//! Write the register statements as Python lists of qubits.
//!
//! Python squin holds a register as a list of qubit references. A lent
//! element is an item of that list, so `borrow`, `release` and `replace`
//! write no line.

use kirin_interpreter::dialect::Interpretable;

use crate::emit::python::{EmitPython, Py, PythonEmitter, PythonError};
use crate::ir::dialects::register::*;

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for AllocRegister {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let size = emitter.text(self.size)?;
        emitter.assign(self.register.into(), &format!("squin.qalloc({size})"))
    }
}

/// Write nothing, because Python squin has no statement that frees a qubit.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for FreeRegister {
    fn interpret(&self, _emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        Ok(())
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Pack {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let wires = self.wires.iter().map(|wire| emitter.text(*wire));
        let wires = wires.collect::<Result<Vec<_>, _>>()?;
        emitter.assign(self.register.into(), &format!("[{}]", wires.join(", ")))
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Split {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (register, index) = (emitter.text(self.register)?, emitter.text(self.index)?);
        emitter.assign(self.before.into(), &format!("{register}[:{index}]"))?;
        emitter.assign(self.after.into(), &format!("{register}[{index}:]"))
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Join {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (first, second) = (emitter.text(self.first)?, emitter.text(self.second)?);
        emitter.assign(self.register.into(), &format!("{first} + {second}"))
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for LengthOf {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let register = emitter.text(self.register)?;
        emitter.alias(self.register_out.into(), self.register)?;
        emitter.assign(self.length.into(), &format!("len({register})"))
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for MeasureRegister {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let register = emitter.text(self.register)?;
        emitter.alias(self.register_out.into(), self.register)?;
        emitter.assign(self.results.into(), &format!("squin.measure({register})"))
    }
}

/// Let the lent wire name the list item at the index.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Borrow {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (register, index) = (emitter.text(self.register)?, emitter.text(self.index)?);
        emitter.bind(self.wire.into(), Py::expr(format!("{register}[{index}]")))?;
        emitter.bind(self.slot.into(), Py::expr(format!("{register}[{index}]")))?;
        emitter.alias(self.register_out.into(), self.register)
    }
}

impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Release {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        emitter.alias(self.register_out.into(), self.register)
    }
}

/// Name the old element, then write the new wire into the list at the index.
impl<'a> Interpretable<PythonEmitter<'a>, EmitPython> for Replace {
    fn interpret(&self, emitter: &mut PythonEmitter<'a>) -> Result<(), PythonError> {
        let (register, index) = (emitter.text(self.register)?, emitter.text(self.index)?);
        let wire = emitter.text(self.wire)?;
        emitter.assign(self.wire_out.into(), &format!("{register}[{index}]"))?;
        emitter.line(format!("{register}[{index}] = {wire}"));
        emitter.alias(self.register_out.into(), self.register)
    }
}
