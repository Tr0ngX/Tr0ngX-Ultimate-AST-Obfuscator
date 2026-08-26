import functools


@functools.lru_cache(maxsize=32, typed=True)
def norm(x):
    return round(x, 2)


a = norm(2.0)
b = norm(2)
print(a, b)
print(norm.cache_info().currsize)
print(norm(2.0) is a)
norm.cache_clear()
print(norm.cache_info().currsize)


@functools.lru_cache(maxsize=None)
def fact(n):
    return 1 if n <= 1 else n * fact(n - 1)


print(fact(10))
