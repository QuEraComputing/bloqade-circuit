from kirin.analysis import const
from kirin.dialects import scf, ilist


def get_scf_for_repeat_count(for_stmt: scf.stmts.For) -> int | None:
    """
    Return the static number of loop iterations for an scf.For iterable when known.
    """
    loop_iterable_hint = for_stmt.iterable.hints.get("const")
    match loop_iterable_hint:
        case const.Value(data=ilist.IList(data=loop_range)) if isinstance(
            loop_range, range
        ):
            return len(loop_range)
        case _:
            return None
