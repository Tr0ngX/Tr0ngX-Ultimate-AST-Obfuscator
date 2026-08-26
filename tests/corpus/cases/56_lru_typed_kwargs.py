from functools import lru_cache


@lru_cache(maxsize=None, typed=True)
def area(w, h):
    return w * h


@lru_cache(maxsize=None, typed=False)
def perim(w, h):
    return 2 * (w + h)


area(2, 3)
area(2.0, 3.0)
perim(2, 3)
perim(2.0, 3.0)
print(area.cache_info().misses, perim.cache_info().misses)
print(area(2, 3) == area(2.0, 3.0))
print(area.cache_parameters()["typed"], perim.cache_parameters()["typed"])

calls = []


@lru_cache(maxsize=2)
def keyed(a, *, b=0):
    calls.append((a, b))
    return a + b


keyed(1, b=5)
keyed(1, b=5)
keyed(2, b=5)
keyed(3, b=5)
keyed(1, b=5)
print(len(calls), calls[0], keyed(1, b=5) == 6)
