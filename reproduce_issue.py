from bloqade import squin
from kirin import rewrite, passes
from kirin.dialects.ilist import IListType
from kirin import types
import ir # This might be wrong, need to find where RemoveEmptyArgGates will be

# I will implement the rule first.

def test_remove_empty_gates():
    @squin.kernel
    def main():
        q = squin.qalloc(2)
        squin.broadcast.h(q)
        squin.broadcast.x([])  # this should be removed

    # main.print()
    # Apply pass here
    pass

if __name__ == "__main__":
    test_remove_empty_gates()
