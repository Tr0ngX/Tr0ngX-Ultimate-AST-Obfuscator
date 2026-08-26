import sys
from functools import lru_cache

sys.setrecursionlimit(200000)


@lru_cache(maxsize=None)
def ack(m, n):
    if m == 0:
        return n + 1
    if n == 0:
        return ack(m - 1, 1)
    return ack(m - 1, ack(m, n - 1))


print(ack(0, 0), ack(1, 5), ack(2, 3), ack(3, 3))
print(ack.cache_info().currsize)
print(ack(2, 4))
