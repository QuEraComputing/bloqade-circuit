OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
rx(pi) q[0];
ry(1.5) q[1];
rz(0.25) q[0];
c[0] = measure q[0];
c[1] = measure q[1];
