from kirin import ir
from kirin.dialects import py


def num_to_py_constant(
    values: list[int | float], stmt_to_insert_before: ir.Statement
) -> list[ir.SSAValue]:

    py_const_ssa_vals = []
    for value in values:
        const_form = py.Constant(value=value)
        const_form.insert_before(stmt_to_insert_before)
        py_const_ssa_vals.append(const_form.result)

    return py_const_ssa_vals
