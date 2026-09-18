"""This module holds the forward analysis that states what each value refers to."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from kirin import ir, types
from kirin.analysis.forward import Forward, ForwardFrame

from bloqade.constants import constant_int

from .lattice import (
    CARRIED,
    UNTRACKED,
    Ref,
    Root,
    Slot,
    Whole,
    Members,
    Unknown,
    Register,
    Returned,
    Positions,
)

KEY = "reference"
"""The registry key of the rules for kirin's own dialects."""


def _inside(root: Root, code: ir.Statement) -> bool:
    """Return True if the function body `code` allocates or receives `root`."""
    node = root.call if isinstance(root, Returned) else root.owner
    if isinstance(node, ir.Block):
        node = node.parent_stmt
    while node is not None:
        if node is code:
            return True
        node = node.parent_stmt
    return False


@dataclass
class ReferenceAnalysis(Forward[Ref], ABC):
    """A forward analysis that states which root each value refers to."""

    keys = (KEY, "absint")
    lattice = Ref

    @abstractmethod
    def kind(self, type_: types.TypeAttribute) -> type[Whole] | type[Register] | None:
        """Return what a value of type `type_` refers to.

        The result is `Whole` for one item of tracked state, `Register` for a
        register of items, and None for a value without tracked state.
        """

    @abstractmethod
    def register_length(self, root: ir.SSAValue, call: Returned | None) -> int | None:
        """Return the static length of the register root `root`, or None.

        If `root` lies inside a callee, `call` names the call of that callee, so
        the length can come from a constant argument of the call.
        """

    def run(
        self, method: ir.Method, *args: Ref, **kwargs: Ref
    ) -> tuple[ForwardFrame[Ref], Ref]:
        """Analyze `method` and every function that it calls.

        Without `args`, each parameter of a tracked type is a root, a tuple
        parameter with a tracked member is `Unknown`, and every other parameter is
        `Untracked`. The returned frame holds the reference of each value of
        `method`, and the returned value is the result of `method`.
        """
        if not args and not kwargs:
            params: list[Ref] = []
            for arg in method.callable_region.blocks[0].args[1:]:
                if (kind := self.kind(arg.type)) is not None:
                    params.append(kind(arg))
                elif (
                    isinstance(arg.type, types.Generic)
                    and arg.type.is_subseteq(types.Tuple)
                    and any(self.kind(member) is not None for member in arg.type.vars)
                ):
                    params.append(Unknown("a member of a tuple parameter"))
                else:
                    params.append(UNTRACKED)
            args = tuple(params)
        return super().run(method, *args, **kwargs)

    def recursion_limit_reached(self) -> Ref:
        """Return `Unknown` for the deepest call of a recursion."""
        return Unknown("the result of a recursive call")

    def method_self(self, method: ir.Method) -> Ref:
        """Return `Untracked` for the method object."""
        return UNTRACKED

    def eval_fallback(
        self, frame: ForwardFrame[Ref], node: ir.Statement
    ) -> tuple[Ref, ...]:
        """Give each tracked result of a statement without a rule `Unknown`."""
        return self.unknown_results(node, f"a value computed by '{node.name}'")

    def unknown_results(self, stmt: ir.Statement, reason: str) -> tuple[Ref, ...]:
        """Return `Unknown` for each tracked result of `stmt` and `Untracked` else."""
        return tuple(
            Unknown(reason) if self.kind(r.type) is not None else UNTRACKED
            for r in stmt.results
        )

    def origin(self, root: Root) -> tuple[ir.SSAValue, Returned | None]:
        """Return the SSA value that allocates or receives `root`, and its call.

        A `Returned` root leads to the root inside the callee, and the innermost
        `Returned` on that path names the call. A root of the analyzed function
        has no call.
        """
        call = None
        while isinstance(root, Returned):
            call = root
            root = root.inner
        return root, call

    def items(self, ref: Ref) -> tuple[Ref, ...] | None:
        """Return the tracked items that `ref` holds, or None if they are unknown.

        One item is itself. A literal list holds its members. A register of static
        length holds one slot per index.
        """
        match ref:
            case Whole() | Slot():
                return (ref,)
            case Members(members):
                return members
            case Register(root):
                size = self.register_length(*self.origin(root))
                if size is not None:
                    return tuple(Slot(root, i) for i in range(size))
        return None

    def index(self, ref: Ref, index: int | ir.SSAValue) -> Ref:
        """Return the reference of the item at `index` of the list or register `ref`.

        A register gives a `Slot`. If the register has a static length, a constant
        index becomes an index in the range 0 to the length minus 1. A literal list
        gives its member at a constant index.
        """
        constant = index if isinstance(index, int) else constant_int(index)
        match ref:
            case Register(root):
                if constant is None:
                    return Slot(root, index)
                size = self.register_length(*self.origin(root))
                if size is None:
                    return Slot(root, constant)
                if not -size <= constant < size:
                    return Unknown("a constant index out of range")
                return Slot(root, constant % size)
            case Members(members):
                if constant is None:
                    return Unknown("a list or tuple read at a runtime index")
                if not -len(members) <= constant < len(members):
                    return Unknown("a constant index out of range")
                return members[constant]
            case Unknown():
                return ref
        return Unknown("an index into a value that is not a register or a list")

    def call_result(self, frame: ForwardFrame[Ref], call: ir.Statement) -> Ref:
        """Return the reference of the result of `call` in the terms of the caller.

        The analysis runs the callee with the caller's references as arguments, like
        kirin's type inference. Kirin gives a call that reaches itself with the same
        references `Bottom` until the result settles, and a recursion that runs to
        kirin's `max_depth` returns `Unknown` from its deepest call.
        """
        callee = call.get_present_trait(ir.StaticCall).get_callee(call)
        args = frame.get_values(call.args)
        _, result = self.call(callee.code, self.method_self(callee), *args)
        return self._returned(call, callee, args, result)

    def _returned(
        self,
        call: ir.Statement,
        callee: ir.Method,
        args: tuple[Ref, ...],
        result: Ref,
    ) -> Ref:
        """Return `result` of `callee` with each root that the callee owns renamed.

        A root that the callee allocates and returns whole at position `p` becomes
        `Returned(call, p)`, where `p` counts the members of a `Positions` result.
        A parameter of the callee is a root only when the callee is the method
        under analysis, in a recursion, and it becomes the root of the argument at
        its position. Every other root that the callee owns is `Unknown`. A slot
        at an index that is a parameter of the callee takes the argument of `call`
        as its index, and a slot at an index that the callee computes is `Unknown`.
        """
        code = callee.code
        params = callee.callable_region.blocks[0].args[1:]
        arguments: dict[ir.SSAValue, ir.SSAValue] = dict(zip(params, call.args))
        passed: dict[ir.SSAValue, Ref] = dict(zip(params, args))
        returned: dict[Root, Root] = {}
        outputs = result.refs if isinstance(result, Positions) else (result,)
        for position, ref in enumerate(outputs):
            if isinstance(ref, (Whole, Register)) and _inside(ref.root, code):
                returned.setdefault(ref.root, Returned(call, position, ref.root))

        def root_in_caller(root: Root) -> Root | None:
            """Return the root as the caller names it, or None if it cannot."""
            if not _inside(root, code):
                return root
            if isinstance(root, ir.SSAValue):
                match passed.get(root):
                    case Whole(named) | Register(named):
                        return named
            return returned.get(root)

        def rename(ref: Ref) -> Ref:
            match ref:
                case Whole(root) | Register(root):
                    if (named := root_in_caller(root)) is None:
                        return Unknown("a root that the callee owns")
                    return type(ref)(named)
                case Slot(root, index):
                    if (named := root_in_caller(root)) is None:
                        return Unknown("a root that the callee owns")
                    if index in arguments:
                        return self.index(Register(named), arguments[index])
                    if isinstance(index, ir.SSAValue) and _inside(index, code):
                        return Unknown("an item at an index that the callee computes")
                    return Slot(named, index)
                case Members(members):
                    return type(ref)(tuple(rename(m) for m in members))
            return ref

        return rename(result)

    def run_loop(
        self,
        frame: ForwardFrame[Ref],
        stmt: ir.Statement,
        body: ir.Region,
        carried: tuple[Ref, ...],
    ) -> tuple[Ref, ...]:
        """Run a loop body until the references that it carries stop changing.

        The body gets `Untracked` for the loop index and the carried references.
        """
        # A join moves a carried reference up, and each one can move up once.
        for _ in range(len(carried) + 1):
            with self.new_frame(stmt, has_parent_access=True) as inner:
                yielded = self.frame_call_region(inner, stmt, body, UNTRACKED, *carried)
            if not isinstance(yielded, tuple) or len(yielded) != len(carried):
                return self.unknown_results(stmt, CARRIED)
            joined = tuple(c.join(y) for c, y in zip(carried, yielded, strict=True))
            if joined == carried:
                frame.entries.update(inner.entries)
                return carried
            carried = joined
        raise AssertionError("a carried reference moved up the lattice twice")
