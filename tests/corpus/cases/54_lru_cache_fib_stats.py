from functools import lru_cache


@lru_cache(maxsize=4)
def cube(n):
    return n ** 3


for v in (1, 2, 3, 4):
    cube(v)
info1 = cube.cache_info()
cube(2)
cube(5)
miss_after = cube.cache_info()
cube(1)
hits = cube.cache_info().hits
print(info1.hits, info1.misses, info1.maxsize, info1.currsize)
print(miss_after.hits, miss_after.misses, miss_after.currsize)
print(hits)
print(cube.cache_clear() or "cleared")
print(cube.cache_info().misses)
