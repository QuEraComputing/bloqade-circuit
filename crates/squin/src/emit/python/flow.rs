//! Write the `if` and loop headers and bind the values that a branch or a loop carries.

use kirin::prelude::*;

use super::{Py, PythonEmitter, PythonError};

impl PythonEmitter<'_> {
    /// Write `if condition:` and `else:` with one arm each, and bind the results.
    ///
    /// Arm argument `k` keeps the name of `inputs[k]`. A classical result gets
    /// a name, and each arm assigns its yield to that name. A wire result
    /// keeps the name of its yield if both arms yield the same qubit name.
    /// Otherwise it gets a name too, and each arm assigns its yield, so code
    /// after the branch acts on the qubit of the arm that ran. The emitter
    /// leaves out an `else` arm that writes no line.
    pub(super) fn branch(
        &mut self,
        condition: SSAValue,
        arms: [Block; 2],
        inputs: &[SSAValue],
        results: &[SSAValue],
    ) -> Result<(), PythonError> {
        let mut names = Vec::new();
        for result in results {
            names.push((!self.linear(*result)).then(|| self.fresh(*result)));
        }
        let condition = self.text(condition)?;
        let mut headers = Vec::new();
        let mut ends = Vec::new();
        let mut yields = Vec::new();
        for (position, arm) in arms.into_iter().enumerate() {
            headers.push(self.line_count());
            self.line(match position {
                0 => format!("if {condition}:"),
                _ => "else:".to_string(),
            });
            for (argument, input) in self.arguments(arm).into_iter().zip(inputs) {
                self.alias(argument, *input)?;
            }
            self.indented(|emitter| {
                emitter.block(arm)?;
                let values = emitter.yields(arm);
                for (name, value) in names.iter().zip(&values) {
                    if let Some(name) = name {
                        let value = emitter.text(*value)?;
                        emitter.line(format!("{name} = {value}"));
                    }
                }
                yields.push(values);
                Ok(())
            })?;
            ends.push(self.line_count());
        }
        let texts = yields
            .iter()
            .map(|values| values.iter().map(|value| self.text(*value)).collect())
            .collect::<Result<Vec<Vec<String>>, _>>()?;
        let mut moved = Vec::new();
        for (position, result) in results.iter().enumerate() {
            if names[position].is_none() && texts[0][position] != texts[1][position] {
                let name = self.fresh(*result);
                moved.push((position, name.clone()));
                names[position] = Some(name);
            }
        }
        // The else arm comes last, so lines that go into it leave the then arm in place.
        for arm in [1, 0] {
            let mut at = ends[arm];
            if !moved.is_empty() && self.only_pass_between(headers[arm], ends[arm]) {
                self.remove_line(headers[arm] + 1);
                at -= 1;
            }
            for (position, name) in &moved {
                let line = format!("{name} = {}", texts[arm][*position]);
                self.insert_line(at, &line);
                at += 1;
            }
        }
        if self.only_pass_between(headers[1], self.line_count()) {
            self.truncate(headers[1]);
        }
        for ((result, name), value) in results.iter().zip(names).zip(&yields[0]) {
            match name {
                Some(name) => self.bind(*result, Py::expr(name))?,
                None => self.alias(*result, *value)?,
            }
        }
        Ok(())
    }

    /// Bind each loop argument: a wire keeps the name of its input, and a
    /// classical value gets a name and an assignment from its input.
    ///
    /// The result holds the name of each classical argument, or `None` for a wire.
    pub(super) fn carried(
        &mut self,
        arguments: &[SSAValue],
        inputs: &[SSAValue],
    ) -> Result<Vec<Option<String>>, PythonError> {
        let mut names = Vec::new();
        for (argument, input) in arguments.iter().zip(inputs) {
            if self.linear(*argument) {
                self.alias(*argument, *input)?;
                names.push(None);
            } else {
                let value = self.text(*input)?;
                let name = self.name(*argument)?;
                self.line(format!("{name} = {value}"));
                names.push(Some(name));
            }
        }
        Ok(names)
    }

    /// Assign each yielded classical value to the loop argument at its position in one line.
    ///
    /// One tuple assignment reads every value before it writes any name, so
    /// a body that swaps two values stays correct.
    pub(super) fn update(
        &mut self,
        carried: &[Option<String>],
        yields: &[SSAValue],
    ) -> Result<(), PythonError> {
        let mut names = Vec::new();
        let mut values = Vec::new();
        for (name, value) in carried.iter().zip(yields) {
            if let Some(name) = name {
                let value = self.text(*value)?;
                if *name != value {
                    names.push(name.clone());
                    values.push(value);
                }
            }
        }
        if !names.is_empty() {
            self.line(format!("{} = {}", names.join(", "), values.join(", ")));
        }
        Ok(())
    }

    /// Let each loop result stand for the loop argument at its position.
    pub(super) fn finish_loop(
        &mut self,
        results: &[SSAValue],
        arguments: &[SSAValue],
    ) -> Result<(), PythonError> {
        for (result, argument) in results.iter().zip(arguments) {
            self.alias(*result, *argument)?;
        }
        Ok(())
    }

    pub(super) fn linear(&self, value: SSAValue) -> bool {
        value.expect_info(self.program).ty().is_linear()
    }

    /// Return the name of `block`, such as `inject` for `^inject`, if it has one.
    pub(super) fn block_name(&self, block: Block) -> Option<String> {
        let symbol = block.expect_info(self.program).name()?;
        let name = self.program.symbol_table().resolve(symbol)?;
        Some(name.to_string())
    }

    pub(super) fn arguments(&self, block: Block) -> Vec<SSAValue> {
        let arguments = block.expect_info(self.program).arguments();
        arguments
            .iter()
            .map(|argument| (*argument).into())
            .collect()
    }

    pub(super) fn yields(&self, block: Block) -> Vec<SSAValue> {
        match block.terminator(self.program) {
            Some(terminator) => terminator.arguments(self.program).copied().collect(),
            None => Vec::new(),
        }
    }
}
