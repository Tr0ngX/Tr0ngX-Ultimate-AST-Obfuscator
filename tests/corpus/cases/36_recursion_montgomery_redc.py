R = 1 << 32


def mont_setup(mod):
    rmod = R % mod
    ninv = pow(-mod, -1, R) & (R - 1)
    return mod, rmod, ninv


def redc(T, mod, ninv):
    m = (T * ninv) & (R - 1)
    t = (T + m * mod) >> 32
    return t - mod if t >= mod else t


def mont_mul(a, b, mod, ninv):
    return redc(a * b, mod, ninv)


mod, rmod, ninv = mont_setup(3233)


def to_mont(x):
    return (x * rmod) % mod


def from_mont(x):
    return mont_mul(x, 1, mod, ninv)


xs = [123, 456, 789]
ys = [987, 654, 321]
naive = [(x * y) % mod for x, y in zip(xs, ys)]
mont = [from_mont(mont_mul(to_mont(x), to_mont(y), mod, ninv)) for x, y in zip(xs, ys)]
print(naive)
print(mont)
print(naive == mont)
sq_naive = [(x * x) % mod for x in xs]
sq_mont = [from_mont(mont_mul(to_mont(x), to_mont(x), mod, ninv)) for x in xs]
print(sq_naive == sq_mont, sq_mont[0])
