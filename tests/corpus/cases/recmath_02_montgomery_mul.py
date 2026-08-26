def mont_mul(a, b, N, Ninv, R):
    T = a * b
    m = (T * Ninv) % R
    t = (T + m * N) // R
    return t - N if t >= N else t


N = 97
R = 128
Ninv = pow(N, -1, R)

xs = [3, 5, 7]
ys = [4, 6, 9]
res = []
for x, y in zip(xs, ys):
    am = (x * R) % N
    bm = (y * R) % N
    cm = mont_mul(am, bm, N, Ninv, R)
    res.append(mont_mul(cm, 1, N, Ninv, R))
print(res)
print(res == [x * y % N for x, y in zip(xs, ys)])
print((N * Ninv) % R == 1)
