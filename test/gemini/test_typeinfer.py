from kirin import types as kirin_types
from kirin.dialects import ilist
from kirin.analysis.typeinfer import TypeInference

from bloqade import squin, types, gemini


def test_type_inference():

    @gemini.logical.kernel(aggressive_unroll=True, num_physical_qubits=4)
    def main():
        q = squin.qalloc(3)

        for i in range(3):
            squin.x(q[i])

        return gemini.logical.terminal_measure(q)

    _, ret_type = TypeInference(main.dialects).run(main)

    assert ret_type.is_structurally_equal(
        ilist.IListType[
            ilist.IListType[types.MeasurementResultType, kirin_types.Literal(4)],
            kirin_types.Literal(3),
        ]
    )
