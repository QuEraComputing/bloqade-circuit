OPENQASM 2.0;
include "qelib1.inc";
qreg q[1];
creg c[1];

if(c == 1) {
    x q[0];
    y q[0];
}
