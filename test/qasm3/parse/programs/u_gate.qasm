OPENQASM 3.0;
include "stdgates.inc";
qubit[1] q;
bit[1] c;
U(pi, 1.5, 0.25) q[0];
c[0] = measure q[0];
