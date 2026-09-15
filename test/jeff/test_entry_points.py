"""What the file boundary accepts and raises, and that written bytes are
independent of the process."""

import sys
import subprocess

import pytest
from kirin import ir, types
from kirin.dialects import func
from kirin.interp.exceptions import InterpreterError

from bloqade import jeff
from bloqade.jeff import JeffImportError, emit_jeff, load_jeff
from bloqade.jeff.types import qureg
from bloqade.jeff.dialects import stmts

from .build import add, entry, method
from .helpers import roundtrips
from .test_roundtrip import bell


def test_emit_takes_a_jeff_program():
    with pytest.raises(TypeError, match="takes a jeff program"):
        emit_jeff(42)  # type: ignore[arg-type]


def test_emit_rejects_an_empty_body():
    block = ir.Block()
    block.args.append_from(types.Any, "self")
    code = func.Function(
        sym_name="empty",
        body=ir.Region(block),
        signature=func.Signature(inputs=(), output=types.NoneType),
    )
    with pytest.raises(TypeError, match="body is empty"):
        emit_jeff(ir.Method(dialects=jeff.kernel, code=code, sym_name="empty"))


def test_every_boundary_type_emits():
    kinds = (types.Int, types.Float, qureg(2), jeff.IntArrayType, jeff.FloatArrayType)
    block, values = entry(*kinds)
    output = types.Generic(
        tuple,
        types.Int,
        types.Float,
        jeff.QuregType,
        jeff.IntArrayType,
        jeff.FloatArrayType,
    )
    assert roundtrips(method(block, tuple(values), output, inputs=kinds))


@pytest.mark.parametrize("kind", [types.Bottom, types.PyClass(str)])
def test_a_boundary_type_without_a_jeff_form_is_refused(kind):
    block, (value,) = entry(kind)
    mt = method(block, value, kind, inputs=(kind,))
    with pytest.raises(InterpreterError):
        emit_jeff(mt)


def test_emit_rejects_a_constant_that_does_not_fit():
    block, _ = entry()
    big = add(block, stmts.ConstInt(value=1 << 40)).result
    with pytest.raises(ValueError, match="does not fit 32 bits"):
        emit_jeff(method(block, big, types.Int))


def test_load_takes_a_path_or_a_module(tmp_path):
    with pytest.raises(TypeError, match="takes a path or a jeff module"):
        load_jeff(42)  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        load_jeff(str(tmp_path / "missing.jeff"))
    path = tmp_path / "bad.jeff"
    path.write_bytes(b"hello")
    with pytest.raises(JeffImportError, match="is not a jeff module"):
        load_jeff(str(path))
    written = tmp_path / "bell.jeff"
    emit_jeff(bell()).write_out(str(written))
    truncated = tmp_path / "cut.jeff"
    truncated.write_bytes(written.read_bytes()[:40])
    with pytest.raises(JeffImportError):
        load_jeff(str(truncated))


def test_a_large_file_reads_back():
    """capnp's default traversal budget is spent by a few hundred operations."""
    block, _ = entry()
    w = add(block, stmts.Alloc()).result
    for _ in range(300):
        (w,) = add(block, stmts.Gate((w,), (), (), gate_name="x")).results
    m = add(block, stmts.MeasureNd(w))
    add(block, stmts.Free(m.result_wire))
    assert roundtrips(method(block, m.bit, types.Bool))


def test_without_the_extra_the_file_boundary_says_how_to_install():
    code = """
import sys

import pytest


class BlockJeffImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "jeff" or fullname.startswith("jeff."):
            raise ImportError("blocked jeff import")
        return None


sys.meta_path.insert(0, BlockJeffImport())

import bloqade.jeff

with pytest.raises(ImportError, match=r"bloqade-circuit\\[jeff\\]") as info:
    bloqade.jeff.load_jeff("any.jeff")
assert "blocked jeff import" in str(info.value.__cause__)
with pytest.raises(ImportError, match=r"bloqade-circuit\\[jeff\\]"):
    bloqade.jeff.emit_jeff(None)
"""
    subprocess.run([sys.executable, "-c", code], check=True)
