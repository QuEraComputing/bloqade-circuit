from bloqade.cirq_utils.lineprog import Variable, LPProblem


def test1():
    v1 = Variable()
    v2 = Variable()

    l1 = v1 + 2 * v2
    l2 = 1 + v2
    l3 = 5 - 2 * v1 - v2

    objective = v1 + v2

    problem = LPProblem()
    problem.add_gez(l1)
    problem.add_gez(l2)
    problem.add_gez(l3)
    problem.add_linear(objective)

    print("Test 1:", problem.solve())


def test2():
    v1 = Variable()

    problem = LPProblem()
    problem.add_quadratic(v1 - 1)
    print("Test 2:", problem.solve())


def test3():
    v1 = Variable()
    problem = LPProblem()
    problem.add_abs(v1 - 1)
    print("Test 3:", problem.solve())
