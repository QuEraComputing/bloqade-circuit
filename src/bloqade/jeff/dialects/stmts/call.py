"""Define the jeff statements that call a function and return from a function.

`Call` mirrors jeff's funcCall operation.
"""

from collections.abc import Sequence

from kirin import ir, types
from kirin.decl import info, statement
from kirin.dialects import func

from bloqade.jeff.types import same_family, same_length
from bloqade.jeff.signature import declared_outputs

dialect = ir.Dialect("jeff.func")


@statement(dialect=dialect)
class Return(ir.Statement):
    """A function terminator that returns the output values of its function."""

    name = "return"
    traits = frozenset({ir.IsTerminator()})

    values: tuple[ir.SSAValue, ...] = info.argument()

    def __init__(self, *values: ir.SSAValue) -> None:
        """Build a terminator that returns `values` from a jeff function."""
        super().__init__(
            args=values,
            args_slice={"values": slice(0, None)},
        )

    def _signature(self) -> func.Signature | None:
        """Return the signature of the enclosing function, or None if there is none."""
        function = self.parent_node
        while function is not None and not isinstance(function, func.Function):
            function = function.parent_node
        return None if function is None else function.signature

    def verify(self) -> None:
        """Check that the return gives as many values as its function declares.

        If the return has no enclosing function or the declared output is `Any`, the
        method checks nothing.
        """
        super().verify()
        signature = self._signature()
        if signature is None or signature.output == types.Any:
            return
        if len(declared_outputs(signature.output)) != len(self.values):
            raise ir.ValidationError(
                self, "the return has not the declared number of values"
            )

    def verify_type(self) -> None:
        """Check that each returned value has the family its function declares."""
        super().verify_type()
        signature = self._signature()
        if signature is None or signature.output == types.Any:
            return
        for value, declared in zip(
            self.values, declared_outputs(signature.output), strict=True
        ):
            if not same_family(value.type, declared) or not same_length(
                value.type, declared
            ):
                raise ir.TypeCheckError(
                    self, f"the return gives {value.type} where {declared} is declared"
                )


@statement(dialect=dialect, init=False)
class Call(ir.Statement):
    """A statement that calls a jeff function.

    The call has one input per parameter and one result per output.
    """

    name = "call"
    callee: ir.Method = info.attribute()
    inputs: tuple[ir.SSAValue, ...] = info.argument()

    def __init__(
        self,
        callee: ir.Method,
        inputs: tuple[ir.SSAValue, ...],
        result_types: Sequence[types.TypeAttribute],
    ) -> None:
        """Build a call of `callee` with `inputs` and one result per result type."""
        super().__init__(
            args=tuple(inputs),
            result_types=tuple(result_types),
            args_slice={"inputs": slice(0, None)},
            attributes={"callee": ir.PyAttr(callee)},
        )

    def verify(self) -> None:
        """Check that the call has one input per parameter and one result per output."""
        super().verify()
        if not isinstance(self.callee, ir.Method):
            raise ir.ValidationError(
                self, f"a call's callee {self.callee!r} is not a method"
            )
        if len(self.callee.self_type.params_type) != len(self.inputs):
            raise ir.ValidationError(
                self, "a call's argument count differs from the callee's"
            )
        output = self.callee.return_type
        if output != types.Any and len(declared_outputs(output)) != len(self.results):
            raise ir.ValidationError(
                self, "a call's result count differs from the callee's"
            )

    def verify_type(self) -> None:
        """Check that each input and result has the family that the callee declares.

        If the callee declares `Any` for a value, the method skips that value.
        """
        super().verify_type()
        params = self.callee.self_type.params_type
        for value, declared in zip(self.inputs, params, strict=True):
            if declared != types.Any and (
                not same_family(value.type, declared)
                or not same_length(value.type, declared)
            ):
                raise ir.TypeCheckError(
                    self,
                    f"a call passes {value.type} where the callee takes {declared}",
                )
        output = self.callee.return_type
        if output == types.Any:
            return
        for result, declared in zip(
            self.results, declared_outputs(output), strict=True
        ):
            if not same_family(result.type, declared) or not same_length(
                result.type, declared
            ):
                raise ir.TypeCheckError(
                    self,
                    f"a call takes {result.type} where the callee returns {declared}",
                )
