def mat_mul(A, B, mod):
    return [
        [
            sum(A[i][k] * B[k][j] for k in range(2)) % mod
            for j in range(2)
        ]
        for i in range(2)
    ]


def mat_pow(M, p, mod):
    result = [[1, 0], [0, 1]]
    base = [[c % mod for c in row] for row in M]
    while p:
        if p & 1:
            result = mat_mul(result, base, mod)
        base = mat_mul(base, base, mod)
        p >>= 1
    return result


def fib_mod(n, mod):
    if n == 0:
        return 0
    M = mat_pow([[1, 1], [1, 0]], n - 1, mod)
    return M[0][0]


def bgcd(a, b):
    if a == 0:
        return b
    if b == 0:
        return a
    shift = ((a | b) & -(a | b)).bit_length() - 1
    a >>= (a & -a).bit_length() - 1
    while b:
        b >>= (b & -b).bit_length() - 1
        if a > b:
            a, b = b, a
        b -= a
    return a << shift


MOD = 10 ** 9 + 7
print([fib_mod(n, MOD) for n in (10, 50, 100)])
print([bgcd(a, b) for a, b in ((48, 18), (17, 5), (270, 192), (1 << 40, 1 << 20))])
