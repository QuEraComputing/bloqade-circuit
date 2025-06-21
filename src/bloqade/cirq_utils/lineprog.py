import dataclasses
from typing import Union
from collections import Counter

import numpy as np
import scipy.sparse
from qpsolvers import solve_qp


class Variable:
    def __add__(
        self, other: Union["Variable", "Expression", float, int]
    ) -> "Expression":
        if isinstance(other, Variable):
            return Expression({self: 1}) + Expression({other: 1})
        elif isinstance(other, Expression):
            return Expression({self: 1}) + other
        elif isinstance(other, (float, int)):
            return Expression({self: 1}) + Expression({None: other})
        else:
            raise TypeError(f"Cannot add {type(other)} to Variable")

    def __radd__(self, left: float | int) -> "Expression":
        return self.__add__(left)

    def __sub__(
        self, other: Union["Variable", "Expression", float, int]
    ) -> "Expression":
        if isinstance(other, Variable):
            return Expression({self: 1}) - Expression({other: 1})
        elif isinstance(other, Expression):
            return Expression({self: 1}) - other
        elif isinstance(other, (float, int)):
            return Expression({self: 1}) - Expression({None: other})
        else:
            raise TypeError(f"Cannot subtract {type(other)} from Variable")

    def __rsub__(self, left: float | int) -> "Expression":
        return self.__sub__(left)

    def __neg__(self) -> "Expression":
        return 0 - self

    def __mul__(self, factor: float | int) -> "Expression":
        if not isinstance(factor, (float, int)):
            raise TypeError("Cannot multiply by non-numeric type")
        return Expression({self: factor})

    def __rmul__(self, factor: float | int) -> "Expression":
        return self.__mul__(factor)

    def __truediv__(self, factor: float | int) -> "Expression":
        if not isinstance(factor, (float, int)):
            raise TypeError("Cannot divide by non-numeric type")
        return Expression({self: 1 / factor})


@dataclasses.dataclass(frozen=True)
class Expression:
    coeffs: dict[Variable | None, float]

    def get(self, key: Variable | None) -> float:
        if key in self.coeffs:
            return self.coeffs[key]
        else:
            return 0

    def __getitem__(self, key: Variable | None) -> float:
        return self.get(key)

    def __add__(
        self, other: Union["Expression", "Variable", float, int]
    ) -> "Expression":
        if isinstance(other, Variable):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[other] = coeff.get(other, 0) + 1
            return Expression(coeffs=coeff)
        elif isinstance(other, Expression):
            coeff = {}
            for key in set(self.coeffs.keys()).union(other.coeffs.keys()):
                coeff[key] = self.coeffs.get(key, 0) + other.coeffs.get(key, 0)
            return Expression(coeffs=coeff)
        elif isinstance(other, (float, int)):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[None] = coeff.get(None, 0) + other
            return Expression(coeffs=coeff)

    def __radd__(self, left: float | int) -> "Expression":
        return self.__add__(left)

    def __sub__(
        self, other: Union["Expression", "Variable", float, int]
    ) -> "Expression":
        if isinstance(other, Variable):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[other] = coeff.get(other, 0) - 1
            return Expression(coeffs=coeff)
        elif isinstance(other, Expression):
            coeff = {}
            for key in set(self.coeffs.keys()).union(other.coeffs.keys()):
                coeff[key] = self.coeffs.get(key, 0) - other.coeffs.get(key, 0)
            return Expression(coeffs=coeff)
        elif isinstance(other, (float, int)):
            coeff = {key: val for key, val in self.coeffs.items()}
            coeff[None] = coeff.get(None, 0) - other
            return Expression(coeffs=coeff)

    def __rsub__(self, left: float | int) -> "Expression":
        return self.__sub__(left)

    def __neg__(self) -> "Expression":
        return 0 - self

    def __mul__(self, factor: float | int) -> "Expression":
        if not isinstance(factor, (float, int)):
            raise TypeError("Cannot multiply by non-numeric type")
        coeff = {key: factor * val for key, val in self.coeffs.items()}
        return Expression(coeffs=coeff)

    def __rmul__(self, factor: float | int) -> "Expression":
        return self.__mul__(factor)


class Solution(dict[Variable, float]): ...


@dataclasses.dataclass(frozen=False)
class LPProblem:
    constraints_eqz: list[Expression] = dataclasses.field(default_factory=list)
    constraints_gez: list[Expression] = dataclasses.field(default_factory=list)
    linear_objective: Expression = dataclasses.field(
        default_factory=lambda: Expression({})
    )
    quadratic_objective: list[Expression] = dataclasses.field(default_factory=list)

    def add_gez(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.constraints_gez.append(expr)
        elif expr < 0:
            raise RuntimeError("No solution found")

    def add_lez(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.constraints_gez.append(-expr)
        elif expr > 0:
            raise RuntimeError("No solution found")

    def add_eqz(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.constraints_eqz.append(expr)
        elif expr != 0:
            raise RuntimeError("No solution found")

    def add_linear(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.linear_objective += expr
        else:
            print("LP Program Warning: no variables in linear objective term")

    def add_quadratic(self, expr: Expression):
        if isinstance(expr, (Expression, Variable)):
            self.quadratic_objective.append(expr)
        else:
            print("LP Program Warning: No variables in quadratic objective term")

    def add_abs(self, expr: Expression):
        """
        Use a slack variable to add an absolute value constraint.
        """
        slack = Variable()
        self.add_gez(slack - expr)
        self.add_gez(slack + expr)
        self.add_gez(1.0 * slack)
        self.add_linear(1.0 * slack)

    def __repr__(self):
        payload = "A Linear programming problem with {:} inequalies, {:} equalities, {:} quadratic".format(
            len(self.constraints_gez),
            len(self.constraints_eqz),
            len(self.quadratic_objective),
        )
        return payload

    @property
    def basis(self) -> list[Variable]:
        all_vars = Counter()
        for expr in self.constraints_eqz:
            all_vars.update(expr.coeffs.keys())
        for expr in self.constraints_gez:
            all_vars.update(expr.coeffs.keys())
        for expr in self.quadratic_objective:
            all_vars.update(expr.coeffs.keys())
        all_vars.update(self.linear_objective.coeffs.keys())
        all_vars.pop(None, None)  # The constant term is not a variable
        all_vars = list(all_vars.keys())
        return all_vars

    def __add__(self, other: "LPProblem") -> "LPProblem":
        if not isinstance(other, LPProblem):
            raise TypeError(f"Cannot add {type(other)} to LPProblem")
        return LPProblem(
            constraints_eqz=self.constraints_eqz + other.constraints_eqz,
            constraints_gez=self.constraints_gez + other.constraints_gez,
            linear_objective=self.linear_objective + other.linear_objective,
            quadratic_objective=self.quadratic_objective + other.quadratic_objective,
        )

    def solve(self) -> Solution:

        basis = self.basis
        if len(basis) == 0:
            return Solution()

        # Generate the sparse matrix for each value...
        # Inequality constraints
        A_gez_dat = []
        A_gez_i = []
        A_gez_j = []
        B_gez_dat = []
        for k in range(len(self.constraints_gez)):
            for key, val in self.constraints_gez[k].coeffs.items():
                if key is not None:
                    A_gez_dat.append(val)
                    A_gez_i.append(k)
                    A_gez_j.append(basis.index(key))
            B_gez_dat.append(self.constraints_gez[k].coeffs.get(None, 0))

        # Equality constraints
        A_eqz_dat = []
        A_eqz_i = []
        A_eqz_j = []
        B_eqz_dat = []
        for k in range(len(self.constraints_eqz)):
            for key, val in self.constraints_eqz[k].coeffs.items():
                if key is not None:
                    A_eqz_dat.append(val)
                    A_eqz_i.append(k)
                    A_eqz_j.append(basis.index(key))
            B_eqz_dat.append(self.constraints_eqz[k].get(None))

        # Linear objective
        C_dat = [self.linear_objective.coeffs.get(key, 0) for key in basis]

        # Quadratic objective
        Q_dat = []
        Q_i = []
        Q_j = []
        for k in range(len(self.quadratic_objective)):
            for key1, val1 in self.quadratic_objective[k].coeffs.items():
                for key2, val2 in self.quadratic_objective[k].coeffs.items():
                    if key1 is not None and key2 is not None:
                        Q_dat.append(val1 * val2)
                        Q_i.append(basis.index(key1))
                        Q_j.append(basis.index(key2))
                    elif key1 is None and key2 is not None:
                        C_dat[basis.index(key2)] += 0.5 * val1 * val2
                    elif key1 is not None and key2 is None:
                        C_dat[basis.index(key1)] += 0.5 * val1 * val2
                    elif key1 is None and key2 is None:
                        # This is the constant term and can be ignored
                        pass
                    else:
                        raise RuntimeError("I should never get here")

        A_gez_mat = scipy.sparse.coo_matrix(
            (A_gez_dat, (A_gez_i, A_gez_j)), shape=(len(B_gez_dat), len(basis))
        ).tocsc()
        B_gez_vec = np.array(B_gez_dat)

        A_eqz_mat = scipy.sparse.coo_matrix(
            (A_eqz_dat, (A_eqz_i, A_eqz_j)), shape=(len(B_eqz_dat), len(basis))
        ).tocsc()
        B_eqz_vec = np.array(B_eqz_dat)

        C_vec = np.array(C_dat)

        Q_mat = scipy.sparse.coo_matrix(
            (Q_dat, (Q_i, Q_j)), shape=(len(basis), len(basis))
        ).tocsc()

        # The quadratic problem uses slightly different variable symbols than
        # scipy, which is why the letters are all off...
        solution = solve_qp(
            P=Q_mat,
            q=C_vec,
            G=-A_gez_mat,
            h=B_gez_vec,
            A=A_eqz_mat,
            b=B_eqz_vec,
            solver="clarabel",
        )
        if solution is None:
            raise RuntimeError("No solution found")

        return Solution(zip(basis, solution))
