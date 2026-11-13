//! Turn SSA names into Python names that do not clash.

use std::collections::HashSet;

/// Hold every Python name that the kernel uses.
#[derive(Default)]
pub(super) struct Names {
    taken: HashSet<String>,
}

impl Names {
    /// Return a new Python name close to the SSA name `ssa`, such as `a0` for `%a0`.
    ///
    /// A name that starts with a digit gets the prefix `v`. A taken name gets
    /// a numeric suffix, as in `a0_1`.
    pub(super) fn fresh(&mut self, ssa: &str) -> String {
        let mut base: String = ssa
            .trim_start_matches('%')
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() { c } else { '_' })
            .collect();
        if base.is_empty() || base.starts_with(|c: char| c.is_ascii_digit()) {
            base = format!("v{base}");
        }
        if is_keyword(&base) {
            base.push('_');
        }
        let mut name = base.clone();
        let mut suffix = 0;
        while self.taken.contains(&name) {
            suffix += 1;
            name = format!("{base}_{suffix}");
        }
        self.taken.insert(name.clone());
        name
    }
}

/// Check whether `name` is a Python keyword or a name that the output itself uses.
///
/// The keywords are the 35 names of Python's `keyword.kwlist`.
fn is_keyword(name: &str) -> bool {
    const KEYWORDS: [&str; 35] = [
        "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class",
        "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global",
        "if", "import", "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return",
        "try", "while", "with", "yield",
    ];
    const USED: [&str; 6] = ["squin", "math", "range", "len", "trunc_div", "trunc_rem"];
    KEYWORDS.contains(&name) || USED.contains(&name)
}
