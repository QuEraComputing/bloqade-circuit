//! Bind each SSA value to the Python expression that stands for it.

use kirin::prelude::*;
use kirin_interpreter::{Env, EnvIndex};

use super::{Py, PythonEmitter, PythonError};
use crate::ir::query;

impl PythonEmitter<'_> {
    /// Give `value` a new Python name, bind it, and return the name.
    pub(super) fn name(&mut self, value: SSAValue) -> Result<String, PythonError> {
        let name = self.fresh(value);
        self.bind(value, Py::expr(name.clone()))?;
        Ok(name)
    }

    /// Return a new Python name for `value` without binding it.
    pub(super) fn fresh(&mut self, value: SSAValue) -> String {
        self.names.fresh(&query::name(self.program, value))
    }

    /// Give `result` a new name and write `name = expression`.
    pub(super) fn assign(&mut self, result: SSAValue, expression: &str) -> Result<(), PythonError> {
        let name = self.name(result)?;
        self.line(format!("{name} = {expression}"));
        Ok(())
    }

    /// Let `value` stand for the Python expression `py`.
    pub(super) fn bind(&mut self, value: SSAValue, py: Py) -> Result<(), PythonError> {
        self.env_write(self.index, value, py)
    }

    /// Let `value` stand for the same expression as `target`.
    pub(super) fn alias(&mut self, value: SSAValue, target: SSAValue) -> Result<(), PythonError> {
        let py = self.get(target)?;
        self.bind(value, py)
    }

    /// Return the expression that stands for `value`.
    pub(super) fn get(&self, value: SSAValue) -> Result<Py, PythonError> {
        self.env_read(self.index, value)
    }

    /// Return the text of the expression that stands for `value`.
    pub(super) fn text(&self, value: SSAValue) -> Result<String, PythonError> {
        Ok(self.get(value)?.text)
    }
}

impl Env for PythonEmitter<'_> {
    type Anchor = SSAValue;

    /// Return the expression of `anchor`, or an error if no rule bound it yet.
    fn env_read(&self, index: EnvIndex, anchor: SSAValue) -> Result<Py, PythonError> {
        self.env.read(index, anchor)?.ok_or_else(|| {
            let name = query::name(self.program, anchor);
            PythonError::Unsupported(format!("the value {name} before its definition"))
        })
    }

    fn env_write(
        &mut self,
        index: EnvIndex,
        anchor: SSAValue,
        data: Py,
    ) -> Result<(), PythonError> {
        Ok(self.env.write(index, anchor, data)?)
    }
}
