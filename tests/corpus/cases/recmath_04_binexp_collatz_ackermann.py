def binpow(b, e):
    if e == 0:
        return 1
    half = binpow(b, e // 2)
    return half * half if e % 2 == 0 else half * half * b


def collatz(n, steps=0):
    if n == 1:
        return steps
    if n % 2 == 0:
        return collatz(n // 2, steps + 1)
    return collatz(3 * n + 1, steps + 1)


def ackermann(m, n):
    if m == 0:
        return n + 1
    if n == 0:
        return ackermann(m - 1, 1)
    return ackermann(m - 1, ackermann(m, n - 1))


print(binpow(3, 13), pow(3, 13))
print([collatz(n) for n in (1, 2, 6, 7, 27)])
print(ackermann(2, 3), ackermann(3, 3))
