import functools


@functools.lru_cache(maxsize=2)
def cube(x):
    return x ** 3


print(cube(1), cube(2), cube(1))
print(cube(3), cube(2))
ci = cube.cache_info()
print(ci.hits, ci.misses, ci.currsize)
print(cube.cache_clear() is None)
print(cube.cache_info().currsize)
