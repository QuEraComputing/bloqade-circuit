"""Convert Jeff through local classical, region and quantum rewrite rules."""

from dataclasses import field, dataclass

from kirin import ir, types
from kirin.passes import Fold, TypeInfer
from kirin.rewrite import Walk
from kirin.dialects import func
from kirin.validation import ValidationSuite
from kirin.rewrite.abc import RewriteRule, RewriteResult
from kirin.dialects.scf.unroll import PickIfElse

from bloqade.jeff.dialects import stmts, kernel as jeff_kernel
from bloqade.squin.wire.group import kernel as wire_kernel
from bloqade.squin.wire.errors import WireConversionError
from bloqade.squin.wire.ownership import mark_owned
from bloqade.jeff.analysis.validation import (
    LinearityValidation,
    StructureValidation,
    JeffToSquinValidation,
)
from bloqade.squin.passes.wire_target import ConversionTarget
from bloqade.squin.rewrite.wire.driver import CheckedFixpoint
from bloqade.squin.analysis.validation.wire import WireValidation

from .jeff2py import JeffToPy
from .rewrite import Retype, Quantum
from .jeff2scf import JeffToScf


@dataclass
class Callees(RewriteRule):
    """Collect direct Jeff callees through Kirin's walker."""

    methods: list[ir.Method] = field(default_factory=list)

    def rewrite_Statement(self, node: ir.Statement) -> RewriteResult:
        """Record a static callee without changing the call."""
        if isinstance(node, stmts.Call):
            self.methods.append(node.callee)
        return RewriteResult()


def reachable(method: ir.Method) -> list[ir.Method]:
    """Order Jeff methods before their callers and reject recursive call graphs."""
    done: dict[ir.Method, None] = {}
    active: set[ir.Method] = set()

    def visit(method):
        if method in active:
            raise WireConversionError(
                "Jeff wire conversion does not support recursive calls.", method.code
            )
        if method in done:
            return
        active.add(method)
        calls = Callees()
        Walk(calls).rewrite(method.code)
        for callee in calls.methods:
            visit(callee)
        active.remove(method)
        done[method] = None

    visit(method)
    return list(done)


@dataclass
class JeffToWire:
    """Convert supported Jeff programs to explicit wire values on private method copies."""

    methods: dict[ir.Method, ir.Method] = field(default_factory=dict, init=False)

    def emit(self, method: ir.Method) -> ir.Method:
        """Return verified wire code with consuming function parameters and explicit result order."""
        self.methods = {}
        if method.dialects is not jeff_kernel:
            raise ValueError("JeffToWire expects jeff.kernel dialects.")
        functions = reachable(method)
        ValidationSuite(
            [StructureValidation, LinearityValidation, JeffToSquinValidation]
        ).validate(method).raise_if_invalid()
        self.methods = {
            source: source.similar(jeff_kernel.union(wire_kernel))
            for source in functions
        }
        for copy in self.methods.values():
            mark_owned(copy)
            JeffToPy(copy.dialects).unsafe_run(copy)
            JeffToScf(copy.dialects).unsafe_run(copy)
            Walk(Retype()).rewrite(copy.code)
            Walk(Quantum(self.methods)).rewrite(copy.code)
            copy.dialects = wire_kernel
            Fold(copy.dialects).unsafe_run(copy)
            CheckedFixpoint(Walk(PickIfElse())).rewrite(copy.code)
            TypeInfer(copy.dialects)(copy)
            assert isinstance(copy.code, func.Function)
            returned = copy.callable_region.blocks[0].last_stmt
            assert isinstance(returned, func.Return)
            inputs = tuple(
                value.type for value in copy.callable_region.blocks[0].args[1:]
            )
            copy.code.signature = func.Signature(
                inputs=inputs, output=returned.value.type
            )
            copy.callable_region.blocks[0].args[0].type = types.MethodType[
                list(inputs), returned.value.type
            ]
            if illegal := ConversionTarget.check(copy):
                raise WireConversionError(
                    "Jeff conversion left unsupported operations: "
                    f"{', '.join(sorted(set(illegal)))}.",
                    copy.code,
                )
            WireValidation().check(copy)
        return self.methods[method]
