import itertools


def naturals():
    n = 1
    while True:
        yield n
        n += 1


def take(it, k):
    return list(itertools.islice(it, k))


print(take(naturals(), 8))
triangular = (n * (n + 1) // 2 for n in naturals())
print(take(triangular, 6))
pairs = ((a, b) for a in naturals() for b in range(a))
print(take(pairs, 7))
