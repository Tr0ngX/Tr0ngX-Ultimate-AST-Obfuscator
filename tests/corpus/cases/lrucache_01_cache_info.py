import functools

calls = []


@functools.lru_cache(maxsize=None)
def fib(n):
    calls.append(n)
    return n if n < 2 else fib(n - 1) + fib(n - 2)


print(fib(15))
print(len(calls))
info = fib.cache_info()
print(info.hits > 0, info.misses == len(calls))
print(fib(15), fib.cache_parameters()["maxsize"])
