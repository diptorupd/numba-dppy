from numba import njit, gdb
import numpy as np
import dpctl


@njit
def f1(a, b):
    c = a + b
    return c


N = 1000
print("N", N)

a = np.ones((N, N), dtype=np.float32)
b = np.ones((N, N), dtype=np.float32)

print("a:", a, hex(a.ctypes.data))
print("b:", b, hex(b.ctypes.data))

with dpctl.device_context("opencl:gpu:0"):
    c = f1(a, b)

print("BIG RESULT c:", c, hex(c.ctypes.data))
for i in range(N):
    for j in range(N):
        if c[i, j] != 2.0:
            print("First index not equal to 2.0 was", i, j)
            break
