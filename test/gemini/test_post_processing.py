import numpy as np
from kirin.dialects import ilist

from bloqade import squin, gemini
from bloqade.gemini.logical import kernel
from bloqade.gemini.post_processing import generate_post_processing


def test_none():

    @kernel
    def main():
        return

    assert generate_post_processing(main) is None


def test_measurements():
    @kernel(num_physical_qubits=2, aggressive_unroll=True)
    def main():
        q = squin.qalloc(2)
        return gemini.logical.terminal_measure(q)

    post_proc = generate_post_processing(main)
    assert post_proc is not None

    # Simulate two shots
    raw_results = np.array([[True, False, True, True], [True, False, False, True]])
    results = list(post_proc(raw_results))
    assert results == [
        ilist.IList([ilist.IList([True, False]), ilist.IList([True, True])]),
        ilist.IList([ilist.IList([True, False]), ilist.IList([False, True])]),
    ]


def test_detectors():
    @kernel(num_physical_qubits=1, aggressive_unroll=True)
    def main():
        q = squin.qalloc(2)
        m = gemini.logical.terminal_measure(q)
        return squin.set_detector(ilist.IList([m[0][0], m[1][0]]), [0, 1])

    post_proc = generate_post_processing(main)
    assert post_proc is not None
    # Simulate two shots
    raw_results = np.array([[True, False], [True, True]])

    results = list(post_proc(raw_results))
    assert results == [True, False]


def test_tuple():
    @kernel(num_physical_qubits=1, aggressive_unroll=True)
    def main():
        q = squin.qalloc(2)
        m = gemini.logical.terminal_measure(q)
        return m, squin.set_detector(ilist.IList([m[0][0], m[1][0]]), [0, 1])

    post_proc = generate_post_processing(main)
    assert post_proc is not None
    # Simulate two shots
    raw_results = np.array([[True, False], [True, True]])
    results = list(post_proc(raw_results))
    assert results == [
        (ilist.IList([ilist.IList([True]), ilist.IList([False])]), True),
        (ilist.IList([ilist.IList([True]), ilist.IList([True])]), False),
    ]
