from typing import Any

from kirin import ir

from .groups import main
from .parse.lowering import QASM2


def loads(
    qasm: str,
    *,
    kernel_name: str = "main",
    returns: str | None = None,
    dialects: ir.DialectGroup | None = None,
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
        returns: (str | None): The return value of the kernel. Defaults to None.
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
    return QASM2(dialects or main).loads(
        qasm,
        kernel_name=kernel_name,
        globals=globals,
        file=file,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
        returns=returns,
    )


def loadfile(
    qasm_file: str,
    *,
    kernel_name: str = "main",
    returns: str | None = None,
    dialects: ir.DialectGroup | None = None,
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
        returns: (str | None): The return value of the kernel. Defaults to None.
        dialects (ir.DialectGroup | None): The dialects to use. Defaults to `qasm2.main`.
        returns (str | None): The return type of the kernel. Defaults to None.
        globals (dict[str, Any] | None): The global variables to use. Defaults to None.
        file (str | None): The file name for error reporting. Defaults to None.
        lineno_offset (int): The line number offset for error reporting. Defaults to 0.
        col_offset (int): The column number offset for error reporting. Defaults to 0.
        compactify (bool): Whether to compactify the output. Defaults to True.
    """
    with open(qasm_file, "r") as f:
        qasm = f.read()
    return loads(
        qasm,
        kernel_name=kernel_name,
        dialects=dialects,
        globals=globals,
        file=file,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
        returns=returns,
    )
