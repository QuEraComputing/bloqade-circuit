import os
import logging
import pathlib
from typing import Any

from kirin import ir, lowering
from kirin.dialects import func

from . import parse
from .groups import main
from .parse.lowering import QASM2


def loads(
    qasm: str,
    *,
    kernel_name: str = "main",
    dialects: ir.DialectGroup | None = None,
    returns: str | None = None,
    globals: dict[str, Any] | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
) -> ir.Method[[], None]:
    """Loads a QASM2 string and returns the corresponding kernel object.

    Args:
        qasm (str): The QASM2 string to load.

    Keyword Args:
        kernel_name (str): The name of the kernel to load. Defaults to "main".
        dialects (ir.DialectGroup | None): The dialects to use. Defaults to `qasm2.main`.
        returns (str | None): The return type of the kernel. Defaults to None.
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.

    Example:

    ```python
    from bloqade import qasm2
    method = qasm2.loads('''
    OPENQASM 2.0;
    qreg q[2];
    creg c[2];
    h q[0];
    cx q[0], q[1];
    measure q[0] -> c[0];
    ''')
    ```
    """
    # TODO: add source info
    stmt = parse.loads(qasm)
    qasm2_lowering = QASM2(dialects or main)
    frame = qasm2_lowering.get_frame(
        stmt,
        source=qasm,
        file=file,
        globals=globals,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
    )

    if returns is not None:
        return_value = frame.get(returns)
        if return_value is None:
            raise lowering.BuildError(f"Cannot find return value {returns}")
    else:
        return_value = func.ConstantNone()
        frame.push(return_value)

    return_node = frame.push(func.Return(value_or_stmt=return_value))

    body = frame.curr_region
    code = func.Function(
        sym_name=kernel_name,
        signature=func.Signature((), return_node.value.type),
        body=body,
    )

    return ir.Method(
        mod=None,
        py_func=None,
        sym_name=kernel_name,
        arg_names=[],
        dialects=qasm2_lowering.dialects,
        code=code,
    )


def loadfile(
    qasm_file: str | pathlib.Path,
    *,
    kernel_name: str = "main",
    dialects: ir.DialectGroup | None = None,
    returns: str | None = None,
    globals: dict[str, Any] | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
) -> ir.Method[[], None]:
    """Loads a QASM2 file and returns the corresponding kernel object. See also `loads`.

    Args:
        qasm_file (str): The QASM2 file to load.

    Keyword Args:
        kernel_name (str): The name of the kernel to load. Defaults to "main".
        dialects (ir.DialectGroup | None): The dialects to use. Defaults to `qasm2.main`.
        returns (str | None): The return type of the kernel. Defaults to None.
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.
    """
    if isinstance(file, pathlib.Path):
        qasm_file_: pathlib.Path = qasm_file  # type: ignore
    else:
        qasm_file_ = pathlib.Path(*os.path.split(qasm_file))

    if not qasm_file_.is_file():
        raise FileNotFoundError(f"File {qasm_file_} does not exist")

    if not qasm_file_.name.endswith(".qasm") or not qasm_file_.name.endswith(".qasm2"):
        logging.warning(
            f"File {qasm_file_} does not end with .qasm or .qasm2. "
            "This may cause issues with loading the file."
        )

    kernel_name = file.name.replace(".qasm", "") if kernel_name is None else kernel_name

    with qasm_file_.open("r") as f:
        source = f.read()

    return loads(
        source,
        kernel_name=kernel_name,
        dialects=dialects,
        returns=returns,
        globals=globals,
        file=file,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
    )
