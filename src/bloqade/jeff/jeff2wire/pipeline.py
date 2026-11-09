"""Convert Jeff through local classical, region and quantum rewrite rules."""

from dataclasses import field, dataclass

from kirin import ir
from kirin.passes import Fold, TypeInfer
from kirin.rewrite import Walk
from kirin.dialects import func
from kirin.validation import ValidationSuite
from kirin.dialects.scf.unroll import PickIfElse

from bloqade.types import output_types
from bloqade.jeff.dialects import stmts, kernel as jeff_kernel
from bloqade.squin.wire.group import kernel as wire_kernel
from bloqade.squin.wire.types import contains_linear
from bloqade.squin.wire.returns import (
    ReturnPolicy,
    set_return_policy,
    quantum_parameter_count,
)
from bloqade.jeff.analysis.validation import (
    LinearityValidation,
    StructureValidation,
    JeffToSquinValidation,
)
from bloqade.squin.rewrite.wire.tools import (
    Retype,
    CheckedFixpoint,
    reachable,
    set_signature,
)
from bloqade.squin.analysis.validation.wire import WireValidation, RegisterValidation

from .jeff2py import JeffToPy
from .rewrite import Quantum, wire_type
from .jeff2scf import JeffToScf


def jeff_callee(node: ir.Statement) -> ir.Method | None:
    """Return the callee of a Jeff `Call`, or None for any other statement."""
    return node.callee if isinstance(node, stmts.Call) else None


@dataclass
class JeffToWire:
    """Convert supported Jeff programs to explicit wire values on private method copies."""

    methods: dict[ir.Method, ir.Method] = field(default_factory=dict, init=False)

    def emit(self, method: ir.Method) -> ir.Method:
        """Return the verified wire copy of `method`, with the wire copies of its callees."""
        self.methods = {}
        if method.dialects is not jeff_kernel:
            raise ValueError("JeffToWire expects jeff.kernel dialects.")
        functions = reachable(method, callee_of=jeff_callee)
        ValidationSuite(
            [StructureValidation, LinearityValidation, JeffToSquinValidation]
        ).validate(method).raise_if_invalid()
        self.methods = {
            source: source.similar(jeff_kernel.union(wire_kernel))
            for source in functions
        }
        for copy in self.methods.values():
            set_return_policy(copy, ReturnPolicy.ExplicitReturns)
            JeffToPy(copy.dialects).unsafe_run(copy)
            JeffToScf(copy.dialects).unsafe_run(copy)
            Walk(Retype(wire_type)).rewrite(copy.code)
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
            set_signature(copy.code, inputs, returned.value.type)
            WireValidation().check(copy)
            if keeps_positions(copy):
                set_return_policy(copy, ReturnPolicy.PreserveArguments)
        return self.methods[method]


def keeps_positions(method: ir.Method) -> bool:
    """Check whether the wire function satisfies `PreserveArguments` without changing its policy.

    The function must return classical values first and then each quantum
    parameter in its position. Its loops and branches must also keep each qubit in
    its position. Then the squin kernel of the function returns no qubits, so it can
    go to Jeff again.
    """
    assert isinstance(method.code, func.Function)
    signature = method.code.signature
    count = quantum_parameter_count(signature)
    outputs = output_types(signature.output) if count else (signature.output,)
    if len(outputs) < count or any(
        contains_linear(typ) for typ in outputs[: len(outputs) - count]
    ):
        return False
    _, errors = RegisterValidation(return_policy=ReturnPolicy.PreserveArguments).run(
        method
    )
    return not errors
