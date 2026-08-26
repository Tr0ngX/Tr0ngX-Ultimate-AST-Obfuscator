import sys
from functools import lru_cache

sys.setrecursionlimit(10000)


@lru_cache(maxsize=None)
def even(n):
    return True if n == 0 else odd(n - 1)


@lru_cache(maxsize=None)
def odd(n):
    return False if n == 0 else even(n - 1)


print(even(50), odd(51), even(7), odd(7))
print(even.cache_info().misses, odd.cache_info().misses)


@lru_cache(maxsize=None)
def paths(r, c):
    if r == 0 or c == 0:
        return 1
    return paths(r - 1, c) + paths(r, c - 1)


print(paths(12, 12))
print(paths.cache_info().hits > 0)
