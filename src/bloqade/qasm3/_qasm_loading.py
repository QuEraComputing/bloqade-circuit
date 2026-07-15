import logging
import pathlib

from kirin import ir
from kirin.types import MethodType
from kirin.dialects import func
from openqasm3.parser import parse as oq3_parse

from .groups import main
from .parse.lowering import QASM3Lowering


def loads(
    qasm: str,
    *,
    kernel_name: str = "main",
    dialects: ir.DialectGroup | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
) -> ir.Method:
    """Parse a QASM3 string and return an ir.Method.

    Args:
        qasm: The OpenQASM 3.0 string to parse.

    Keyword Args:
        kernel_name: The name of the kernel. Defaults to "main".
        dialects: The dialect group to use. Defaults to `qasm3.main`.
        file: The file name for error reporting. Defaults to None.
        lineno_offset: The line number offset for error reporting. Defaults to 0.
        col_offset: The column number offset for error reporting. Defaults to 0.
        compactify: Whether to compactify the output. Defaults to True.

    Example:

    ```python
    from bloqade import qasm3
    method = qasm3.loads('''
    OPENQASM 3.0;
    qubit[2] q;
    bit[2] c;
    h q[0];
    cx q[0], q[1];
    c[0] = measure q[0];
    c[1] = measure q[1];
    ''')
    ```
    """
    ast = oq3_parse(qasm)
    qasm3_lowering = QASM3Lowering(dialects or main)
    frame = qasm3_lowering.get_frame(
        ast,
        source=qasm,
        file=file,
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
    )

    return_value = func.ConstantNone()
    frame.push(return_value)
    frame.push(func.Return(value_or_stmt=return_value))

    body = frame.curr_region
    code = func.Function(
        sym_name=kernel_name,
        signature=func.Signature((), return_value.result.type),
        body=body,
    )

    body.blocks[0].args.append_from(MethodType, kernel_name + "_self")

    mt = ir.Method(
        sym_name=kernel_name,
        dialects=qasm3_lowering.dialects,
        code=code,
    )

    mt.verify()
    return mt


def loadfile(
    qasm_file: str | pathlib.Path,
    *,
    kernel_name: str | None = "main",
    dialects: ir.DialectGroup | None = None,
    file: str | None = None,
    lineno_offset: int = 0,
    col_offset: int = 0,
    compactify: bool = True,
) -> ir.Method:
    """Load an OpenQASM 3.0 file and return an ir.Method. See also `loads`.

    Args:
        qasm_file: Path to the OpenQASM 3.0 file.

    Keyword Args:
        kernel_name: The name of the kernel. Defaults to "main".
        dialects: The dialect group to use. Defaults to `qasm3.main`.
        file: The file name for error reporting. Defaults to None.
        lineno_offset: The line number offset for error reporting. Defaults to 0.
        col_offset: The column number offset for error reporting. Defaults to 0.
        compactify: Whether to compactify the output. Defaults to True.
    """
    if isinstance(qasm_file, str):
        qasm_file_ = pathlib.Path(qasm_file)
    else:
        qasm_file_ = qasm_file

    if not qasm_file_.is_file():
        raise FileNotFoundError(f"File {qasm_file_} does not exist")

    suffix = qasm_file_.suffix
    if suffix not in (".qasm", ".qasm3"):
        logging.warning(
            f"File {qasm_file_} does not end with .qasm or .qasm3. "
            "This may cause issues with loading the file."
        )

    if kernel_name is None:
        kernel_name = qasm_file_.stem

    with qasm_file_.open("r") as f:
        source = f.read()

    return loads(
        source,
        kernel_name=kernel_name,
        dialects=dialects,
        file=file or str(qasm_file_),
        lineno_offset=lineno_offset,
        col_offset=col_offset,
        compactify=compactify,
    )
