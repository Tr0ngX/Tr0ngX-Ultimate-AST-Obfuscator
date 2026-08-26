def egcd(a, b):
    if b == 0:
        return (a, 1, 0)
    g, x, y = egcd(b, a % b)
    return (g, y, x - (a // b) * y)


def inv_mod(a, m):
    g, x, _ = egcd(a % m, m)
    if g != 1:
        return None
    return x % m


g, x, y = egcd(240, 46)
print(g, x, y, 240 * x + 46 * y)
print(inv_mod(3, 11), inv_mod(4, 8))
print(inv_mod(17, 3120))
